"""Extract each model's 4-class verdict per task from a set of runs and write a wide CSV (one
row per task, one column per model) for consensus analysis. Handles both task pipelines:

  tasks_answer/  — built with `build_tasks.py --include-answer` from silver_patients.csv; the
                   prompt bakes in the rubric and does NOT ask for confidence. Run once to
                   generate the model-consensus ground-truth labels + trajectories.
  tasks/         — regular experiment runs, built from patients.csv; the prompt DOES ask for a
                   confidence line.

Both use the same 4 classes: Yes / No / Indeterminate – lack of data / Indeterminate – medical
ambiguity. Each Harbor trial writes verifier/report.md opening with a verdict line like
`## Answer: Indeterminate – lack of data` (also seen: `Verdict: **No**`, en-dash or hyphen, a
trailing "(out of scope …)"). Experiment reports also carry `## Confidence: 87%`. A trial with
no report.md is ERROR; a report with no parseable verdict is UNPARSEABLE (folded to ERROR in the
CSV, listed on stdout). The `*_conf` columns appear only when some report stated a confidence.

Silver labels come from each scenario's cohort CSV — both silver_patients.csv and patients.csv are
indexed, so tasks from either pipeline map back (task ids are `<scenario_id>-<param-hash>`, see
taskids.py). Silver may be 3-class (silver_patients.csv → YES/NO/ESCALATE) or 4-class
(patients.csv → the two indeterminate subtypes); `models_disagree_silver` is a true 4-way match
(subtypes distinct), except a subtype-less 3-class ESCALATE silver accepts either indeterminate.

  python construction/scripts/analyze_labels.py                 # auto-discovers the full_answer_* runs
  python construction/scripts/analyze_labels.py jobs/exp_a jobs/exp_b   # explicit dirs (experiment runs)
  python construction/scripts/analyze_labels.py --out labels.csv ...
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tomllib
from collections import Counter
from pathlib import Path

from clinicare_core import load_full, task_id

SCRIPTS = Path(__file__).resolve().parent  # construction/scripts/
CONSTRUCTION = SCRIPTS.parent  # construction/
ROOT = CONSTRUCTION.parent  # repo root
BENCHMARK = ROOT / "benchmark"
SCENARIOS_DIR = BENCHMARK / "_scenarios"
JOBS_DIR = ROOT / "jobs"

# The four canonical model labels, plus silver's merged-indeterminate label.
REAL_LABELS = ("YES", "NO", "INDETERMINATE_LACK_OF_DATA", "INDETERMINATE_MEDICAL_AMBIGUITY")
SILVER_LABELS = ("YES", "NO", "ESCALATE")

# The verdict marker line, kept IN SYNC with _template/tests/judge.py::_extract_outcome_label:
# a heading/bold "Answer"/"Verdict"/… label at the START of a line (only markdown punctuation
# before it, so an in-prose "...is a clear Yes" never matches), then the answer slot.
VERDICT_MARKER = re.compile(
    r"^[\s#>*_`\-]*(?:final\s+answer|answer|verdict|determination)\b\s*[:\-–—.)]?\s*(.*)$",
    re.IGNORECASE,
)
# Stated confidence line, e.g. `## Confidence: 97%` (also `**Confidence: 97%`). Anchored at line
# start so prose like "the 3% confidence gap" doesn't match; captures the number (drops %).
CONFIDENCE_RE = re.compile(
    r"^\s*[#>*\s]*confidence\b[^0-9]*?([0-9]+(?:\.[0-9]+)?)\s*%?",
    re.IGNORECASE,
)


def labels_in_slot(slot: str) -> set[str]:
    """The distinct 4-class labels named in a verdict slot. More than one ⇒ the agent listed
    several (ambiguous / gaming) ⇒ caller treats it as unparseable. A bare 'Indeterminate' with
    no subtype names no resolvable label — the instruction requires the specific subtype."""
    s = slot.lower()
    found: set[str] = set()
    if "indetermin" in s:
        if "lack" in s or "insufficient data" in s:
            found.add("INDETERMINATE_LACK_OF_DATA")
        if "ambig" in s or "medical" in s:
            found.add("INDETERMINATE_MEDICAL_AMBIGUITY")
    if re.search(r"\byes\b", s):
        found.add("YES")
    if re.search(r"\bno\b", s):
        found.add("NO")
    return found


def report_path(trial: Path) -> Path:
    """Where the agent's report lands, which depends on the verifier.

    A normal run writes verifier/report.md. A run with `verifier: disable` (used for the oracle
    label pass, where only the verdict is needed and the LLM judges are pure cost) has no verifier/
    directory at all — the report is collected as an artifact instead. Returning the verifier path
    when neither exists keeps parse_report's ERROR behaviour for a genuinely missing report."""
    for p in (trial / "verifier" / "report.md", trial / "artifacts" / "verifier" / "report.md"):
        if p.exists():
            return p
    return trial / "verifier" / "report.md"


def parse_report(report: Path) -> tuple[str, str]:
    """(verdict, confidence) from a report. verdict is one of REAL_LABELS, ERROR (missing/empty),
    or UNPARSEABLE. Anti-gaming (in sync with the judge): only the FIRST verdict-marker line is
    authoritative, and its slot must name exactly one label — a line listing several is
    UNPARSEABLE, so dumping all labels can't match the key. confidence is the first stated value
    ("" when absent, as in the answer pipeline)."""
    if not report.exists():
        return "ERROR", ""
    text = report.read_text(errors="replace")
    if not text.strip():
        return "ERROR", ""
    lines = text.splitlines()
    verdict = "UNPARSEABLE"

    def _slot_verdict(i, m):
        slot = m.group(1)
        if not slot.strip():  # "## Answer\nYes" split — use the next non-empty line
            for nxt in lines[i + 1 :]:
                if nxt.strip():
                    slot = nxt
                    break
        found = labels_in_slot(slot)
        return found.pop() if len(found) == 1 else "UNPARSEABLE"

    # Prefer a heading verdict marker (## Answer / ### Answer), else the first marker of any kind.
    # Kept IN SYNC with judge.py::_extract_outcome_label.
    for headings_only in (True, False):
        matched = False
        for i, line in enumerate(lines):
            if headings_only and not line.lstrip().startswith("#"):
                continue
            m = VERDICT_MARKER.match(line)
            if m:
                verdict = _slot_verdict(i, m)
                matched = True
                break
        if matched:
            break
    conf = ""
    for line in lines:
        c = CONFIDENCE_RE.match(line)
        if c:
            conf = c.group(1)
            break
    return verdict, conf


def collapse_indeterminate(label: str) -> str:
    """Fold to the shared 3-class vocabulary (YES / NO / ESCALATE); the whole indeterminate family
    → ESCALATE. Used only for the subtype-less ground-truth case in label_match."""
    u = label.upper()
    if u in ("YES", "NO"):
        return u
    if "INDETERM" in u or "ESCALATE" in u:
        return "ESCALATE"
    return u


def label_match(model: str, silver: str) -> bool:
    """True 4-way match between a model verdict and the silver label — the two indeterminate
    SUBTYPES are distinct and must match exactly. The one concession: a 3-class ESCALATE silver
    (silver_patients.csv, subtypes merged) accepts either indeterminate; a 4-class silver
    (patients.csv) is matched exactly. Kept in sync with judge.py::_label_match."""
    m = (model or "").upper()
    s = (silver or "").upper()
    if not m or not s:
        return False
    if m == s:
        return True
    return s == "ESCALATE" and collapse_indeterminate(m) == "ESCALATE"


def model_label(job_dir: Path) -> str:
    """Short, readable column name for the model a job ran (derived from its eval key)."""
    res = json.loads((job_dir / "result.json").read_text())
    key = next(iter(res.get("stats", {}).get("evals", {})), "")  # e.g. codex__gpt-5.5__tasks_answer
    model = key.split("__")[1] if "__" in key else (key or job_dir.name)
    for short in ("opus", "gpt", "gemini", "sonnet", "haiku"):
        if short in model.lower():
            return short
    return model or job_dir.name


def task_id_of(trial_dir: Path) -> str:
    """`advanced-imaging-006__hRH3j8L` -> `advanced-imaging-006` (hash is after the `__`)."""
    return trial_dir.name.rsplit("__", 1)[0]


def split_scenario(tid: str) -> str:
    """Scenario id from a task id by stripping the trailing `-<hash>`. Only a fallback — prefer the
    `scenario` from silver_lookup when present."""
    m = re.match(r"^(.*)-[0-9a-fA-F]+$", tid)
    return m.group(1) if m else tid


def param_columns() -> list[str]:
    """The union of every scenario's `params`, for the CSV's per-task ID columns. Ordered with the
    common ID columns first, then any others in first-seen order — so new params (stay_id,
    k_anchor_time, procedure_time, window_start/end, …) show up automatically."""
    seen: list[str] = []
    for d in sorted(SCENARIOS_DIR.iterdir()):
        toml = d / "scenario.toml"
        if not toml.exists():
            continue
        for p in tomllib.loads(toml.read_text()).get("params", []):
            if p not in seen:
                seen.append(p)
    pref = ["subject_id", "hadm_id", "stay_id", "note_id"]
    return [p for p in pref if p in seen] + [p for p in seen if p not in pref]


def silver_lookup() -> dict[str, dict]:
    """task_id -> {scenario, silver, **params}.

    The gold cohort comes from the bundle's full750.csv. Each scenario's transient
    silver_patients.csv (select_cohort.py output, the pre-adjudication sampling stratifier) is
    layered UNDER it where present, so tasks from an answer-pipeline run over the silver pool
    still resolve — but a bundle row always wins, because the bundle is the adjudicated label
    and silver is only a stratifier.
    """
    out: dict[str, dict] = {}

    # silver first, so the bundle overwrites it on collision.
    for d in SCENARIOS_DIR.iterdir():
        toml, pts = d / "scenario.toml", d / "silver_patients.csv"
        if not (toml.exists() and pts.exists()):
            continue
        scenario = tomllib.loads(toml.read_text())
        scenario_id, params = scenario["id"], scenario["params"]
        with pts.open(newline="") as fh:
            for row in csv.DictReader(fh):
                out[task_id(scenario_id, params, row)] = {
                    "scenario": scenario_id,
                    "silver": row.get("expected_label", ""),
                    **{p: row.get(p, "") for p in params},
                }

    for row in load_full():
        out[row["task_id"]] = {
            "scenario": row["scenario_id"],
            "silver": row["expected_label"],
            **{
                k: v
                for k, v in row.items()
                if k not in ("task_id", "scenario_id", "expected_label")
            },
        }
    return out


def agreement(labels: list[str]) -> tuple[str, str]:
    """(agreement_kind, consensus_label) over the models' 4-class labels. ERROR/UNPARSEABLE are
    ignored for the vote; consensus is the strict majority (> half of the models present)."""
    real = [x for x in labels if x in REAL_LABELS]
    if not real:
        return ("none", "")
    c = Counter(real)
    top, n = c.most_common(1)[0]
    if len(real) == len(labels) and len(c) == 1:
        return ("unanimous", top)
    if n > len(labels) / 2:
        return ("majority", top)
    return ("split", "")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jobs", nargs="*", help="job dirs (default: jobs/full_answer_*)")
    ap.add_argument("--out", default=str(CONSTRUCTION / "label_agreement.csv"))
    args = ap.parse_args()

    job_dirs = [Path(j) for j in args.jobs] or (
        sorted(JOBS_DIR.glob("full_answer_*")) or sorted(JOBS_DIR.glob("golden_answer_*"))
    )
    job_dirs = [j for j in job_dirs if (j / "result.json").exists()]
    if not job_dirs:
        sys.exit("no job dirs found (looked for jobs/full_answer_* then jobs/golden_answer_*)")

    models = [model_label(j) for j in job_dirs]
    print("Models:", ", ".join(f"{m} ({j.name})" for m, j in zip(models, job_dirs)))

    silver = silver_lookup()
    table: dict[str, dict[str, str]] = {}  # task_id -> {model: label}
    conf: dict[str, dict[str, str]] = {}  # task_id -> {model: confidence-string}
    unparseable: list[tuple[str, str]] = []
    for model, jd in zip(models, job_dirs):
        for trial in jd.glob("*__*"):
            if not trial.is_dir():
                continue
            tid = task_id_of(trial)
            label, confidence = parse_report(report_path(trial))
            if label == "UNPARSEABLE":
                unparseable.append((model, trial.name))
                label = "ERROR"
            table.setdefault(tid, {})[model] = label
            conf.setdefault(tid, {})[model] = confidence

    # Overlay support: a model can appear in more than one passed dir (e.g. a base sweep followed
    # by a boundary rerun). The build loop processed dirs in order, so a later dir's verdict for a
    # given (task, model) already overwrote the earlier one in `table` — pass base dirs FIRST and
    # rerun dirs LAST to make the rerun win. Collapse the now-duplicated model tags to one column
    # per model (first-seen order) so the output + consensus vote count each model once.
    models = list(dict.fromkeys(models))

    # Confidence columns only when at least one report stated one (i.e. the experiment pipeline).
    has_conf = any(conf[t].get(m) for t in conf for m in models)

    out_path = Path(args.out)
    param_cols = param_columns()
    model_cols = [c for m in models for c in ((m, f"{m}_conf") if has_conf else (m,))]
    cols = [
        "task_id",
        "scenario",
        *param_cols,
        "silver",
        *model_cols,
        "agreement",
        "consensus",
        "models_disagree_silver",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for tid in sorted(table):
            meta = silver.get(tid, {})
            scenario = meta.get("scenario") or split_scenario(tid)
            labels = [table[tid].get(m, "ERROR") for m in models]
            agr, cons = agreement(labels)
            sil = meta.get("silver", "")
            # True 4-way match (subtypes distinct), with a subtype-less 3-class ESCALATE silver
            # accepting either indeterminate. See label_match.
            disagree = (
                sum(1 for x in labels if x in REAL_LABELS and not label_match(x, sil))
                if sil
                else ""
            )
            per_model = [
                v
                for m in models
                for v in (
                    (table[tid].get(m, "ERROR"), conf[tid].get(m, ""))
                    if has_conf
                    else (table[tid].get(m, "ERROR"),)
                )
            ]
            w.writerow(
                [
                    tid,
                    scenario,
                    *[meta.get(pc, "") for pc in param_cols],
                    meta.get("silver", ""),
                    *per_model,
                    agr,
                    cons,
                    disagree,
                ]
            )

    # ---- summary to stdout ----
    print(f"\nWrote {len(table)} tasks -> {out_path}")
    print("\nPer-model label distribution:")
    for m in models:
        c = Counter(table[t].get(m, "ERROR") for t in table)
        print(f"  {m:10} " + "  ".join(f"{k}={c.get(k, 0)}" for k in (*REAL_LABELS, "ERROR")))
    if has_conf:
        print("\nPer-model confidence (over reports that stated one):")
        for m in models:
            vals = [float(conf[t][m]) for t in conf if conf[t].get(m)]
            if vals:
                print(
                    f"  {m:10} n={len(vals):<4} mean={sum(vals) / len(vals):.1f}  "
                    f"min={min(vals):g}  max={max(vals):g}"
                )
            else:
                print(f"  {m:10} (no confidence values found)")
    agrs = Counter()
    consensus = Counter()
    for tid in table:
        labels = [table[tid].get(m, "ERROR") for m in models]
        kind, cons = agreement(labels)
        agrs[kind] += 1
        if kind in ("unanimous", "majority"):
            consensus[cons] += 1
    print("\nAgreement across models:")
    for k in ("unanimous", "majority", "split", "none"):
        print(f"  {k:10} {agrs.get(k, 0)}")
    print("\nConsensus-label distribution (unanimous + majority tasks):")
    for k in REAL_LABELS:
        print(f"  {k:34} {consensus.get(k, 0)}")
    if unparseable:
        print(f"\n{len(unparseable)} report(s) present but no parseable verdict (recorded ERROR):")
        for m, name in unparseable[:20]:
            print(f"  [{m}] {name}")


if __name__ == "__main__":
    main()
