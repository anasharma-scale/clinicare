"""Generate Harbor tasks from scenario templates × patient cohorts.

Source of truth is _scenarios/ (one dir per scenario: scenario.toml + a cohort CSV + an optional
rubrics.toml) and _template/ (shared task.toml / instruction_appendix*.md / tests/{test.sh,
judge.py}). For each scenario this renders one task per row of the cohort CSV, id'd
`<scenario_id>-<param-hash>` (see taskids.py) so the same patient always maps to the same task id
across cohort CSVs. Output dirs are build artifacts (gitignored) — never edit or commit them;
re-run after changing a scenario or cohort.

Two render modes:
  - default            → tasks/        : the agent sees only the simple-query `prompt`.
  - --include-answer   → tasks_answer/ : the prompt PLUS the full rubric (clinical_question
                        + the four 4-class label-rule lists) baked in, so a capable
                        agent's output can serve as a reference answer (used to generate the
                        model-consensus ground-truth labels).

Each build gets its own directory, so none can overwrite another: `--no-policy` appends
`_nopolicy` and `--per-label` (the dev subset) gives `tasks_dev_policy/` / `tasks_dev_nopolicy/`.

Every task also gets a process-rubric verifier: `tests/judge.py` plus a per-task
`tests/rubrics.json` bundling the scenario's process rubric (rubrics.toml), the patient's
`expected_label`, and the scenario spec. The judge scores a deterministic outcome (verdict vs
label) plus an LLM-graded process rubric; a scenario with no rubrics.toml still builds (the judge
records a 'no rubrics' skip).

Cohort rows come from the gated bundle's full750.csv (`--cohort`, or CLINICARE_COHORT_DIR). The
output dir is fixed by the build MODE, never by which CSV you pass, so rebuild whenever you want
a different cohort in a given dir. See DATA_ACCESS.md for obtaining the bundle.

A full build (no scenario args) always starts from a clean target dir. Naming specific scenarios
does a surgical rebuild of just those scenarios, leaving the rest of the dir untouched.

Credential isolation: the credentialed `mimic-tools` sidecar is emitted as ONE shared
`<out_dir>/_sidecar.compose.yml` (from _template/environment/sidecar.compose.yml, with the resolved
env-image ref + absolute corpus path baked in) — NOT a per-task environment/docker-compose.yaml. A
DOCKER run wires it via `harbor run --extra-docker-compose <out_dir>/_sidecar.compose.yml`; a MODAL
run ignores it and reaches a self-hosted sidecar via MIMIC_TOOLS_URL. Keeping it out of each task's
environment/ is what lets ONE build serve BOTH backends — a per-task compose would force modal into
compose mode (DinD), which disables network_mode=allowlist. The agent reaches MIMIC only through the
proxy shim and holds no creds (see packages/mimic_tools/SIDECAR.md). `--no-policy` sets
MIMIC_POLICY_TOOLS=0 (policy-off ablation); the corpus mount is inert then.

  python benchmark/scripts/build_tasks.py                      # every scenario, agent mode, from the bundle
  python benchmark/scripts/build_tasks.py post-ct-aki ...      # only the named scenario id(s)
  python benchmark/scripts/build_tasks.py --include-answer     # bake the rubric in → tasks_answer/
  python benchmark/scripts/build_tasks.py --cohort /path/to/full750.csv   # explicit bundle path
  python benchmark/scripts/build_tasks.py --no-policy          # policy-off ablation build
  python benchmark/scripts/build_tasks.py --workers 1          # serial build (readable traceback on failure)

Build time is dominated by filesystem round trips, not CPU: tasks are rendered by a thread pool
(--workers, default 32) and the identical tests/ files are hardlinked rather than written (see
TestFiles). On a network filesystem the difference is large; on local disk it barely matters.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import threading
import tomllib
import urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from clinicare_core import by_scenario, param_key, task_id

# env_image is a sibling module, not a package import: it content-hashes this repo's Dockerfile
# and mimic_tools sources by walking up from its own path, so it stays next to its one caller.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_image import image_ref, image_tag, tag_exists  # noqa: E402

HEALTHCARE = Path(__file__).resolve().parent.parent  # benchmark/ (scripts/ lives under it)
SCENARIOS_DIR = HEALTHCARE / "_scenarios"
TEMPLATE_DIR = HEALTHCARE / "_template"
# The corpus is assembled locally, not repo content (benchmark/corpus/README.md);
# CLINICARE_CORPUS_DIR points at the directory acquire_corpus.py built.
CORPUS_DIR = Path(os.environ.get("CLINICARE_CORPUS_DIR") or (HEALTHCARE / "corpus"))
POLICY_GOLD = HEALTHCARE / "eval" / "gold" / "policy_gold.json"  # per-scenario policy docs
CORPUS_MANIFEST = HEALTHCARE / "corpus_manifest.csv"  # the corpus membership authority
# The credential-isolation sidecar, copied into each task as environment/docker-compose.yaml (Harbor
# auto-merges it). Its ${MIMIC_ENV_IMAGE} is replaced with the resolved env ref at build time.
SIDECAR_COMPOSE = TEMPLATE_DIR / "environment" / "sidecar.compose.yml"
SIDECAR_IMAGE_PLACEHOLDER = "${MIMIC_ENV_IMAGE}"

NAME_PLACEHOLDER = 'name = "mimic/<task-id>"'
DESC_PLACEHOLDER = 'description = "<one-line task summary>"'
# The env image ref is NOT hardcoded in the template — it is injected here from env_image.py (a
# content hash of the Dockerfile + mimic_tools, or the $MIMIC_ENV_TAG pin) so the tag can't drift
# from what was pushed and there's no committed tag line to merge-conflict on. See env_image.py.
IMAGE_PLACEHOLDER = 'docker_image = "<env-image-ref>"'
HOSTS_PLACEHOLDER = 'allowed_hosts = ["<allowed-hosts>"]'
# The agent container is egress-locked to exactly these hosts. The sidecar alias is not optional
# — without it the agent cannot reach the tools at all — so it is always appended rather than
# left to the operator to remember. Everything else is the model endpoint(s): the three vendor
# APIs by default, plus whatever gateway the *_BASE_URL vars name, plus $CLINICARE_ALLOWED_HOSTS.
DEFAULT_MODEL_HOSTS = ("api.anthropic.com", "api.openai.com", "generativelanguage.googleapis.com")
SIDECAR_HOST = "mimic-tools.internal"
# Setting one of these is an explicit statement that the run should talk to that endpoint, so its
# host is allowlisted automatically. Keep in step with run_sweep.BASE_URL_VAR, which forwards them.
MODEL_BASE_URL_VARS = ("ANTHROPIC_BASE_URL", "OPENAI_BASE_URL", "GOOGLE_GEMINI_BASE_URL")


def gateway_hosts() -> list[tuple[str, str]]:
    """[(var, host)] for each *_BASE_URL currently set — the gateways this build must be able to reach."""
    out = []
    for var in MODEL_BASE_URL_VARS:
        url = os.environ.get(var, "").strip()
        if not url:
            continue
        # urlsplit needs a scheme to populate .hostname; a bare "host:port" parses as scheme:path.
        host = urllib.parse.urlsplit(url if "//" in url else f"//{url}").hostname
        if host:
            out.append((var, host))
    return out


def allowed_hosts() -> list[str]:
    """Model endpoints + the sidecar alias, baked into every task at build time.

    Harbor does not ${VAR}-interpolate allowed_hosts, so this list is frozen at build time and a
    gateway exported afterwards is NOT reachable — the egress sidecar blocks it, and the agent
    reports a TLS/certificate error minutes later rather than a refusal. Deriving the gateway hosts
    from the *_BASE_URL vars here is what stops "I set the base URL" and "the build allows it" from
    being two separate things you have to remember to do.
    """
    raw = os.environ.get("CLINICARE_ALLOWED_HOSTS", "").strip()
    hosts = [h.strip() for h in raw.split(",") if h.strip()] if raw else list(DEFAULT_MODEL_HOSTS)
    origin = {h: "CLINICARE_ALLOWED_HOSTS" for h in hosts}
    added = []
    for var, host in gateway_hosts():
        if host not in hosts:
            hosts.append(host)
            origin[host] = var
            added.append((var, host))
    # Validate AFTER deriving the gateway hosts, so a typo'd base URL ("localhost:8000",
    # "not-a-url") is caught here rather than baked in as a bare label — which some Harbor
    # backends reject outright, killing every trial before its first tool call. Before the
    # announcement below, so we never report allowlisting a host we then refuse.
    if bare := [h for h in hosts if "." not in h]:
        sys.exit(
            "allowed_hosts entries must be dotted hostnames; got "
            + ", ".join(f"{h!r} (from {origin[h]})" for h in bare)
            + ". A bare label is rejected by some Harbor backends and silently kills every trial."
        )
    for var, host in added:
        print(f"  allowlisting {host} (from {var})")
    if SIDECAR_HOST not in hosts:
        hosts.append(SIDECAR_HOST)
    return hosts


# Tasks are rendered by a thread pool (see build_scenario), so per-task validation failures can't just
# sys.exit — they'd die inside a worker thread. They raise this instead and build_scenario exits on it.
DEFAULT_WORKERS = 32  # each task is ~25 filesystem round trips of pure latency, not CPU work


class BuildError(Exception):
    """A per-task validation failure, raised from a worker thread and turned into a build abort."""


class Template:
    """The shared boilerplate rendered into every generated task.

    Only the per-task-*substituted* text lives here. The three byte-identical test files are
    not text at all — TestFiles hardlinks them (see below).
    """

    def __init__(self, toml: str, appendix: str, policy_appendix: str) -> None:
        self.toml = toml
        self.appendix = appendix
        self.policy_appendix = policy_appendix


def load_template(include_answer: bool) -> Template:
    toml = (TEMPLATE_DIR / "task.toml").read_text()
    hosts_line = "allowed_hosts = [" + ", ".join(f'"{h}"' for h in allowed_hosts()) + "]"
    for ph in (NAME_PLACEHOLDER, DESC_PLACEHOLDER, IMAGE_PLACEHOLDER, HOSTS_PLACEHOLDER):
        if ph not in toml:
            sys.exit(f"_template/task.toml is missing the expected placeholder: {ph!r}")
    toml = toml.replace(HOSTS_PLACEHOLDER, hosts_line)
    # Answer mode uses a separate appendix (no confidence ask, more prescriptive answer format).
    appendix_name = (
        "instruction_appendix_answer.md" if include_answer else "instruction_appendix.md"
    )
    appendix = (TEMPLATE_DIR / appendix_name).read_text()
    # Policy-tool guidance is a separate appendix so it's only included in the policy-ON build.
    policy_appendix = (TEMPLATE_DIR / "instruction_policy.md").read_text()
    if SIDECAR_IMAGE_PLACEHOLDER not in SIDECAR_COMPOSE.read_text():
        sys.exit(
            f"{SIDECAR_COMPOSE.name} is missing the image placeholder {SIDECAR_IMAGE_PLACEHOLDER!r} "
            f"— build_tasks bakes the resolved env ref there."
        )
    return Template(toml, appendix, policy_appendix)


class TestFiles:
    """Installs the IDENTICAL template test files into each task's tests/.

    They are hardlinked, not written: repeating judge.py (~41 KB) + policy_scoring.py (~31 KB)
    per task is the build's single biggest cost on a network filesystem. A hardlink shares the
    inode (same FS),
    so every consumer sees a normal file — unlike a symlink, this is transparent to Harbor's
    tests upload — and test.sh keeps the template's 0o755 mode.

    Filesystems cap links per inode, and the cap is CUMULATIVE ACROSS OUTPUT DIRS: tasks/,
    tasks_dev/ and tasks_answer/ all link the same _template inode, so the template eventually
    saturates and os.link raises EMLINK. The cap varies wildly by filesystem — some network
    filesystems allow as few as 177, where 750 tasks x 3 output dirs hits it easily. Hence the
    rotating source per file —
    link until the current source saturates, then copy ONCE and link the next batch against that
    fresh copy (~1 copy per 176 tasks instead of one per task). Also covers EXDEV, for an
    out_dir on a different filesystem than the template.

    Called from build_scenario's worker threads, so the rotating source is lock-guarded — but only on
    the rare rotation, never on the hot link path.
    """

    NAMES = ("test.sh", "judge.py", "policy_scoring.py", "evidence.py")

    def __init__(self) -> None:
        self._src = {n: TEMPLATE_DIR / "tests" / n for n in self.NAMES}
        self._lock = threading.Lock()
        self.copies = 0  # reported by main(); a count near the task total means linking is broken

    def install(self, tests_dir: Path) -> None:
        for name in self.NAMES:
            dst = tests_dir / name
            src = self._src[name]
            try:
                os.link(src, dst)
                continue
            except OSError:
                pass  # source is out of links (EMLINK) or on another filesystem (EXDEV)
            # Rotate under the lock so racing threads produce ONE fresh source between them, not one
            # each: if another thread already rotated, its source has link budget — just use it.
            with self._lock:
                if self._src[name] is not src:
                    try:
                        os.link(self._src[name], dst)
                        continue
                    except OSError:
                        pass
                shutil.copy2(TEMPLATE_DIR / "tests" / name, dst)
                self._src[name] = dst
                self.copies += 1


def write_sidecar_compose(out_dir: Path, env_ref: str) -> None:
    """Write the ONE shared sidecar compose a DOCKER run passes via `--extra-docker-compose`.

    Deliberately NOT per-task: a per-task environment/docker-compose.yaml forces Harbor's MODAL
    provider into compose mode (DinD + host networking), which disables network_mode=allowlist. As a
    single top-level file it never lands in a task's environment/, so task dirs stay backend-neutral —
    modal ignores it (it reaches a self-hosted sidecar via MIMIC_TOOLS_URL) and needs no allowlist edit.
    Bakes the resolved image ref + absolute corpus path so the file is self-contained (a docker run
    supplies only MIMIC_API_SECRET + MIMIC_DATA_ROOT at runtime). MIMIC_POLICY_TOOLS follows each task's
    [environment.env] via ${VAR}, so policy-on/off needs no separate compose.
    """
    text = SIDECAR_COMPOSE.read_text()
    if SIDECAR_IMAGE_PLACEHOLDER not in text or "./policy_corpus" not in text:
        sys.exit(
            f"{SIDECAR_COMPOSE.name} must contain {SIDECAR_IMAGE_PLACEHOLDER!r} and './policy_corpus' "
            f"for build_tasks to bake the env ref + corpus path."
        )
    text = text.replace(SIDECAR_IMAGE_PLACEHOLDER, env_ref).replace(
        "./policy_corpus", str(CORPUS_DIR.resolve())
    )
    (out_dir / "_sidecar.compose.yml").write_text(text)


def load_policy_gold() -> dict[str, list[str]]:
    """{scenario_id: [governing corpus doc filenames]} from eval/gold/policy_gold.json.

    Missing file → {} (policy scoring then has no gold for any scenario and is skipped by the judge).
    """
    if not POLICY_GOLD.exists():
        print(
            f"  note: {POLICY_GOLD.name} not found — policy grounding will be skipped",
            file=sys.stderr,
        )
        return {}
    data = json.loads(POLICY_GOLD.read_text())
    return {g["scenario_id"]: list(g.get("policy_docs", [])) for g in data}


def check_corpus(policy_gold: dict[str, list[str]]) -> None:
    """Fail the build if CORPUS_DIR cannot satisfy the policy gold.

    CORPUS_DIR is bind-mounted whole into the trial container, and the sidecar serves every *.md
    in it as a policy document (minus README.md, which is documentation about the corpus). The
    directory's contents are therefore the agent's searchable world, and two mismatches matter:

    A missing governing document makes its rubric unsatisfiable for every agent, which the
    benchmark would otherwise report as a model weakness rather than a corpus defect -- fatal.
    An unexpected extra .md silently becomes a distractor nobody chose -- a warning only, since
    intended distractors are legitimately absent from the gold and cannot be told apart here.
    """
    if not CORPUS_DIR.is_dir():
        sys.exit(f"corpus dir not found: {CORPUS_DIR} (set CLINICARE_CORPUS_DIR)")

    present = {p.name for p in CORPUS_DIR.glob("*.md")} - {"README.md"}
    governing = {doc for docs in policy_gold.values() for doc in docs}

    if missing := sorted(governing - present):
        sys.exit(
            f"{len(missing)} governing document(s) named in {POLICY_GOLD.name} are absent from "
            f"{CORPUS_DIR}:\n  " + "\n  ".join(missing)
        )

    # The manifest lists every document the corpus is meant to contain, governing or distractor,
    # so anything outside it arrived by accident -- a stray .md dropped in the directory, or a
    # bundle shipping its own notes alongside the documents.
    expected = set()
    if CORPUS_MANIFEST.is_file():
        with CORPUS_MANIFEST.open(newline="") as fh:
            expected = {r["filename"].strip() for r in csv.DictReader(fh)}

    if expected and (extra := sorted(present - expected)):
        print(
            f"  note: {len(extra)} corpus document(s) are absent from {CORPUS_MANIFEST.name} and "
            f"will act as unintended distractors: {', '.join(extra)}",
            file=sys.stderr,
        )
    print(f"  corpus: {len(present)} documents, {len(governing)} governing")


def load_rubrics(
    scenario_dir: Path, scenario_id: str, filename: str = "rubrics.toml", kind: str = "process"
) -> list[dict]:
    """Load a scenario's rubric file → [{id, title, weight}, ...]. Used for both the process rubric
    (``rubrics.toml``) and the policy-relevance rubric (``policy_rubrics.toml``).

    A missing file is allowed (returns []): the judge records a 'no rubrics' skip for that
    axis. (The deterministic outcome/citation scores are still produced.)
    """
    rubrics_path = scenario_dir / filename
    if not rubrics_path.exists():
        print(
            f"  note: {scenario_id} has no {filename} — {kind} rubric will be skipped",
            file=sys.stderr,
        )
        return []
    data = tomllib.loads(rubrics_path.read_text())
    rubrics = data.get("rubric", [])
    out = []
    for r in rubrics:
        missing = [k for k in ("id", "title", "weight") if k not in r]
        if missing:
            sys.exit(f"{scenario_id}/{filename} has a rubric missing field(s) {missing}: {r}")
        item = {"id": r["id"], "title": r["title"], "weight": r["weight"]}
        if "kind" in r:  # policy rubric items carry a grader selector (relevance / citation_*)
            item["kind"] = r["kind"]
        out.append(item)
    if not out:
        print(
            f"  warning: {scenario_id}/{filename} declares no [[rubric]] entries", file=sys.stderr
        )
    return out


# The 4-class label rules, shared by answer_spec_block (agent-facing, in --include-answer) and
# reference_spec_block (judge-facing). (title, scenario.toml key) pairs, in verdict order.
_LABEL_RULES = (
    ("Yes", "inclusion_criteria"),
    ("No", "exclusion_criteria"),
    ("Indeterminate – lack of data", "indeterminate_lack_of_data_criteria"),
    ("Indeterminate – medical ambiguity", "indeterminate_medical_ambiguity_criteria"),
)


def reference_spec_block(scenario: dict) -> str:
    """The operationalized 4-class label rule passed to the judge as the grading reference."""
    lines: list[str] = []
    for title, key in _LABEL_RULES:
        items = scenario.get(key) or []
        if items:
            lines.append(f"Answer {title} if:")
            lines += [f"- {it.strip()}" for it in items]
            lines.append("")
    return "\n".join(lines).strip()


def render_prompt(prompt: str, params: list[str], row: dict, tag: str) -> str:
    text = prompt.strip()
    for p in params:
        val = (row.get(p) or "").strip()
        if not val:
            raise BuildError(f"[{tag}] cohort row has an empty value for param {p!r}")
        text = text.replace("{" + p + "}", val)
    if "{" in text and "}" in text:  # a placeholder for a param not declared in `params`
        raise BuildError(f"[{tag}] unresolved placeholder remains after substitution: {text!r}")
    return text


def answer_spec_block(scenario: dict, process_rubrics: list[dict]) -> str:
    """The reference spec appended to the prompt in --include-answer mode: the operationalized
    4-class label rules plus the process rubric, required evidence, and grounding requirements —
    the full 'answer key' so a capable model's output can serve as a reference solution. Each
    section is emitted only when the scenario supplies it."""
    lines = [
        "## Reference specification",
        "",
        "Apply the rubric below as the definitive standard — it supersedes any "
        '"decide for yourself" wording in the question above. Work the case fully, then '
        "give the Yes / No / Indeterminate answer the criteria dictate, with cited evidence.",
        "",
    ]
    if scenario.get("clinical_question"):
        lines += [f"**Clinical question.** {scenario['clinical_question'].strip()}", ""]
    for title, key in _LABEL_RULES:
        items = scenario.get(key) or []
        if items:
            lines.append(f"Answer **{title}** if:")
            lines += [f"- {it.strip()}" for it in items]
            lines.append("")
    if process_rubrics:
        lines.append(
            "**Process rubric.** Your report and methodology are graded against these items — "
            "MUST-DO items (positive weight) earn credit when performed; MUST-NOT items (negative "
            "weight) lose credit when committed:"
        )
        lines += [f"- ({r['weight']}) [{r['id']}] {r['title'].strip()}" for r in process_rubrics]
        lines.append("")
    evidence = scenario.get("required_evidence") or []
    if evidence:
        lines.append("**Required evidence.** Retrieve and cite:")
        lines += [f"- {it.strip()}" for it in evidence]
        lines.append("")
    grounding = (scenario.get("grounding_requirements") or "").strip()
    if grounding:
        lines += ["**Grounding requirements.**", grounding, ""]
    return "\n".join(lines).strip()


def build_scenario(
    scenario_dir: Path,
    template: Template,
    out_dir: Path,
    include_answer: bool,
    rows: list[dict],
    policy_on: bool,
    env_ref: str,
    test_files: TestFiles,
    policy_gold: dict[str, list[str]],
    workers: int = DEFAULT_WORKERS,
    per_label: int = 0,
    drop_process_rubric: bool = False,
) -> tuple[str, int]:
    scenario = tomllib.loads((scenario_dir / "scenario.toml").read_text())
    scenario_id, description, params, prompt = (
        scenario["id"],
        scenario["description"],
        scenario["params"],
        scenario["prompt"],
    )
    for p in params:
        if "{" + p + "}" not in prompt:
            print(f"  warning: param {p!r} never appears in {scenario_id} prompt", file=sys.stderr)

    if not rows:
        print(f"  {scenario_id}: no cohort rows — skipping", file=sys.stderr)
        return scenario_id, 0
    missing = [p for p in params if p not in rows[0]]
    if missing:
        sys.exit(
            f"{scenario_id}: cohort rows are missing value(s) for declared params {missing}. "
            "The bundle's params_json and scenario.toml's `params` have diverged."
        )

    if per_label:  # stratified dev subset: first `per_label` rows per expected_label class
        kept: list[dict] = []
        label_seen: Counter = Counter()
        for r in rows:
            lab = (r.get("expected_label") or "").strip()
            if label_seen[lab] < per_label:
                kept.append(r)
                label_seen[lab] += 1
        rows = kept

    process_rubrics = load_rubrics(scenario_dir, scenario_id)
    # --no-process-rubric drops the (contributor-pending, unvalidated) process rubric from the ORACLE
    # PROMPT so the reference labels are determined by the trusted 4-class criteria, not shaky rubric
    # scaffolding — process_rubrics still go into rubrics.json below for the verifier / candidate eval.
    prompt_rubrics = [] if drop_process_rubric else process_rubrics
    spec_block = answer_spec_block(scenario, prompt_rubrics) if include_answer else None
    reference_spec = reference_spec_block(scenario)
    clinical_question = (scenario.get("clinical_question") or "").strip()

    # Policy grounding: the scenario's governing corpus docs (gold) and whether the agent is
    # EXPECTED to cite policy — only in a policy-ON build AND when the scenario has gold docs.
    # Drives the condition-aware policy outcome rubric in the judge (policy-off ⇒ expect none).
    policy_gold_docs = policy_gold.get(scenario_id, [])
    policy_expected = bool(policy_on and policy_gold_docs)
    # Authored (seeded then expert-refined) policy-relevance rubric, LLM-judged on policy-ON.
    policy_rubrics = load_rubrics(scenario_dir, scenario_id, "policy_rubrics.toml", "policy")

    # Clear this scenario's existing tasks first so a shrunk patient list leaves no stragglers.
    for stale in out_dir.glob(f"{scenario_id}-*"):
        shutil.rmtree(stale)

    # Resolve every task id up front (pure CPU) so a hash collision aborts before any I/O.
    seen: dict[str, str] = {}  # task_id -> param_key, to catch hash collisions within the scenario
    tids: list[str] = []
    for row in rows:
        tid = task_id(scenario_id, params, row)
        key = param_key(params, row)
        if seen.get(tid, key) != key:
            sys.exit(
                f"[{scenario_id}] task-id hash collision: {seen[tid]!r} and {key!r} both hash to "
                f"{tid!r} — bump HASH_LEN in clinicare_core.taskids and rebuild."
            )
        seen[tid] = key
        tids.append(tid)

    # Same for every task in the build: policy-tool guidance is appended (both modes) only in a
    # policy-ON build.
    tail = template.appendix + (("\n\n" + template.policy_appendix) if policy_on else "")

    def write_task(tid: str, row: dict) -> None:
        query = render_prompt(prompt, params, row, tid)
        if include_answer:
            instruction = query + "\n\n---\n\n" + spec_block + "\n\n" + tail
        else:
            instruction = query + "\n\n" + tail

        task_dir = out_dir / tid
        (task_dir / "tests").mkdir(parents=True, exist_ok=True)
        # Task dirs are BACKEND-NEUTRAL — no per-task environment/docker-compose.yaml. A per-task
        # compose would force Harbor's MODAL provider into compose mode (DinD + host networking), which
        # DISABLES network_mode=allowlist (modal.py: `network_allowlist = not _compose_mode`). Instead
        # the credential-isolation sidecar is ONE shared _sidecar.compose.yml (written once in main());
        # a DOCKER run passes it via `--extra-docker-compose`, while MODAL reaches a self-hosted sidecar
        # via MIMIC_TOOLS_URL and needs no compose at all. So one build serves both backends.
        # (Empty environment/ kept for Harbor's prebuilt-image path.)
        (task_dir / "environment").mkdir(parents=True, exist_ok=True)
        (task_dir / "instruction.md").write_text(instruction)
        task_toml = (
            template.toml.replace(NAME_PLACEHOLDER, f'name = "mimic/{tid}"')
            .replace(DESC_PLACEHOLDER, f"description = {json.dumps(description)}")
            .replace(IMAGE_PLACEHOLDER, f'docker_image = "{env_ref}"')
        )
        if not policy_on:  # flip the template's policy-on default to the off ablation
            task_toml = task_toml.replace('MIMIC_POLICY_TOOLS = "1"', 'MIMIC_POLICY_TOOLS = "0"')
        (task_dir / "task.toml").write_text(task_toml)

        test_files.install(task_dir / "tests")

        # Per-task rubric bundle the judge reads. `query` (not the appendix-laden
        # instruction) is the clinical question the process rubrics grade against.
        rubrics_bundle = {
            "task_id": tid,
            "scenario_id": scenario_id,
            "prompt": query,
            "clinical_question": clinical_question,
            "reference_spec": reference_spec,
            "ground_truth_label": (row.get("expected_label") or "").strip(),
            "process_rubrics": process_rubrics,
            "policy_gold_docs": policy_gold_docs,
            "policy_expected": policy_expected,
            "policy_rubrics": policy_rubrics,
        }
        (task_dir / "tests" / "rubrics.json").write_text(json.dumps(rubrics_bundle, indent=2))

    # Writing a task is ~25 filesystem round trips and no real CPU, so fan the rows out: threads overlap
    # that latency (the GIL is released across every syscall) for a large speedup on a network FS.
    # pool.map re-raises the first worker exception here, so a BuildError still aborts the build.
    try:
        if workers > 1:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(write_task, tids, rows))
        else:  # --workers 1: serial, for a readable traceback when a scenario won't build
            for tid, row in zip(tids, rows):
                write_task(tid, row)
    except BuildError as e:
        sys.exit(str(e))
    return scenario_id, len(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("scenarios", nargs="*", help="scenario id(s) to build (default: all)")
    ap.add_argument(
        "--include-answer",
        action="store_true",
        help="bake the full rubric into each prompt (for reference answers) → tasks_answer/",
    )
    ap.add_argument(
        "--cohort",
        default=None,
        help="path to the bundle's full750.csv (default: $CLINICARE_COHORT_DIR/full750.csv)",
    )
    ap.add_argument(
        "--no-policy",
        action="store_true",
        help="policy-OFF ablation: stage no corpus and set MIMIC_POLICY_TOOLS=0 in each task",
    )
    ap.add_argument(
        "--no-process-rubric",
        action="store_true",
        help="drop the process rubric from the ORACLE PROMPT (answer mode) so reference labels are "
        "set by the trusted 4-class criteria, not the contributor-pending rubric scaffolding. The "
        "rubric still lands in rubrics.json for the verifier / candidate eval.",
    )
    ap.add_argument(
        "--no-env-check",
        action="store_true",
        help="skip the preflight that verifies the resolved env image tag is available to run",
    )
    ap.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"threads rendering tasks in parallel (default {DEFAULT_WORKERS}). Task writing is "
        "latency-bound, so this is the main build-time lever; 1 forces a serial build with a "
        "readable traceback.",
    )
    ap.add_argument(
        "--per-label",
        type=int,
        default=0,
        help="stratified DEV subset: keep only the first N patients per expected_label class "
        "per scenario → tasks_dev_policy/ or tasks_dev_nopolicy/ (both conditions are named here, "
        "so bare tasks_dev/ is unreachable). Leaves the full tasks/ untouched. Task ids are "
        "stable, so dev results pool with full runs. e.g. --per-label 2 → 25 scenarios × ~6 = "
        "~150 tasks.",
    )
    args = ap.parse_args()

    # Resolve the env image ref once (content hash of the Dockerfile + mimic_tools, or the
    # $MIMIC_ENV_TAG pin) and confirm it is actually runnable, so a build can't silently bake a
    # tag no Docker daemon can supply. A local image counts; a registry is consulted only when
    # the repo names one. tag_exists returns None when it cannot tell (no docker, daemon down,
    # registry unreachable) — that degrades to a warning, so offline builds still work.
    env_ref, env_tag = image_ref(), image_tag()
    if not args.no_env_check:
        exists = tag_exists(env_tag)
        if exists is False:
            sys.exit(
                f"env image {env_ref} is not available to run (tag {env_tag!r}).\n"
                f"  Build it first:  MIMIC_ENV_TAG={env_tag} bash scripts/build_image.sh\n"
                f"  or pin an existing tag:  MIMIC_ENV_TAG=<tag> {Path(__file__).name} …\n"
                f"  or bypass this check:    --no-env-check"
            )
        if exists is None:
            print(f"  note: could not verify {env_ref} is available — proceeding", file=sys.stderr)
        else:
            print(f"  env image: {env_ref} ✓")
    else:
        print(f"  env image: {env_ref} (availability check skipped)")

    base = "tasks_answer" if args.include_answer else "tasks"
    # Policy-off always gets its own directory so the ablation can't overwrite the build it is
    # compared against. Policy-on keeps the bare name: `tasks/` is run_sweep's default and
    # `tasks_answer/` is what the oracle configs mount. The dev path names both conditions,
    # since neither is a default there.
    policy_on = not args.no_policy
    off_suffix = "" if policy_on else "_nopolicy"
    dev_suffix = "_policy" if policy_on else "_nopolicy"
    out_dir = HEALTHCARE / (f"{base}_dev{dev_suffix}" if args.per_label else f"{base}{off_suffix}")
    template = load_template(args.include_answer)

    scenario_dirs = sorted(d for d in SCENARIOS_DIR.iterdir() if (d / "scenario.toml").exists())
    if args.scenarios:
        want = set(args.scenarios)
        scenario_dirs = [
            d
            for d in scenario_dirs
            if tomllib.loads((d / "scenario.toml").read_text())["id"] in want
        ]
        if not scenario_dirs:
            sys.exit(f"no scenarios matched {sorted(want)}")

    # A full build regenerates everything, so start clean (this also drops tasks for scenarios that
    # no longer exist). A partial build (specific scenarios) is surgical — build_scenario clears just the
    # scenarios it rebuilds, leaving the rest of out_dir alone.
    if not args.scenarios and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # One shared sidecar compose for docker runs (`--extra-docker-compose <out_dir>/_sidecar.compose.yml`).
    # Rewritten every build so the baked image ref stays current; modal runs ignore it.
    write_sidecar_compose(out_dir, env_ref)

    # `policy_on` is hoisted to the out_dir composition above (it has to be known to name the dir).
    # Read once and share across scenarios: both are build-wide inputs, not per-scenario state.
    policy_gold = load_policy_gold()
    if policy_on and policy_gold:
        check_corpus(policy_gold)
    test_files = TestFiles()
    # One read for the whole build. by_scenario preserves file order, which --per-label depends
    # on: it takes the first N rows per label class, so row order decides the stratified subset.
    cohort = by_scenario(args.cohort)
    unknown = sorted(
        set(cohort)
        - {
            tomllib.loads((d / "scenario.toml").read_text())["id"]
            for d in SCENARIOS_DIR.iterdir()
            if (d / "scenario.toml").is_file()
        }
    )
    if unknown:
        sys.exit(f"cohort references scenario id(s) with no scenario dir: {unknown}")
    total = 0
    for d in scenario_dirs:
        scenario_id, n = build_scenario(
            d,
            template,
            out_dir,
            args.include_answer,
            cohort.get(tomllib.loads((d / "scenario.toml").read_text())["id"], []),
            policy_on,
            env_ref,
            test_files,
            policy_gold,
            args.workers,
            args.per_label,
            args.no_process_rubric,
        )
        print(f"  {scenario_id}: {n} task(s)")
        total += n
    mode = "answer" if args.include_answer else "agent"
    policy = "policy-on" if policy_on else "policy-off"
    rubric = ", no-process-rubric" if args.no_process_rubric else ""
    subset = f", dev {args.per_label}/label" if args.per_label else ""
    print(
        f"built {total} {mode} ({policy}{rubric}{subset}) task(s) across {len(scenario_dirs)} scenario(s) → {out_dir}"
    )
    # One copy per ~176 tasks is normal at a 177-link cap; one per task means linking is broken.
    linked = total * len(TestFiles.NAMES) - test_files.copies
    print(f"  test files: {linked} linked, {test_files.copies} copied")


if __name__ == "__main__":
    main()
