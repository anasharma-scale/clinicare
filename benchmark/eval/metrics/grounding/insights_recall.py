"""insights_recall — finding coverage (R_finding in the paper).

Did the agent's report surface the evidence the task requires? Built on the medical expert's
REQUIRED-EVIDENCE rubric
(build_required_evidence.py → required_evidence.json): a per-scenario list of decisive evidence
CATEGORIES the report must cover. This is DRBench's insights_recall (coverage of key insights)
adapted so the gold is the expert's required-evidence checklist rather than a hand-authored
insight set.

  insights_recall = (# required categories the report covers) / (# required categories)   [per trace]

Coverage is judged category-by-category by an LLM against the report text (batched, with a
retry if the response doesn't cover all categories). The rubric is SCENARIO-LEVEL; per-patient
specifics inside a category (which creatinine values, which dates) are the domain of the
deterministic core / insight_grounding. This scores category coverage only.

This measures COVERAGE (did the report address the required evidence), NOT faithfulness — a
report can "cover" a category with a wrong value; insight_grounding checks correctness.

Creds: OpenAI SDK → judge endpoint from .env (shared with the other metrics);
JUDGE_MODEL / --model overrides (default openai/gpt-5.5).

  cd <repo root>
  python benchmark/eval/metrics/grounding/insights_recall.py \
      --traces benchmark/eval/traces \
      --rubric benchmark/eval/gold/required_evidence.json --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from clinicare_core import load_env
from clinicare_core.paths import bootstrap

HERE = Path(__file__).resolve().parent

bootstrap(__file__, "grounding", "eval")
from core.scenarios import slug_from_trial_dir  # noqa: E402
from insight_grounding_llm import _call, _json_array, make_client  # noqa: E402

_MAX_RETRIES = 3


def load_rubric(path: Path) -> dict:
    """slug -> {task, task_name, source, categories:[...]}."""
    return json.loads(Path(path).read_text())


_COVERAGE_PROMPT = """A clinical deep-research report is scored on whether it COVERS each piece \
of REQUIRED EVIDENCE a medical expert says the task needs. For each numbered requirement, decide \
whether the report addresses it — i.e. presents that evidence or an explicit finding about it \
(including a stated negative/absence when that is what's required). Judge COVERAGE, not \
correctness: a requirement is covered even if the specific value might be wrong; it is NOT \
covered if the report is silent on it.

REPORT:
{report}

REQUIRED EVIDENCE:
{reqs}

Return ONLY a JSON array, one object per requirement IN ORDER:
[{{"i": 1, "covered": true, "why": "<brief: where/how, or why not>"}}, ...]
"""


def coverage(client, model: str, report: str, categories: list[str]) -> list[dict]:
    """One judgment per category (covered bool). Retries if the response omits indices."""
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(categories))
    prompt = _COVERAGE_PROMPT.format(report=report, reqs=numbered)
    by_i: dict[int, dict] = {}
    last_exc: Exception | None = None
    for _ in range(_MAX_RETRIES):
        try:
            out = _json_array(_call(client, model, prompt))
        except Exception as e:  # noqa: BLE001  (parse/API failure → re-roll)
            last_exc = e
            continue
        for o in out:
            if isinstance(o, dict) and "i" in o:
                try:
                    by_i.setdefault(int(o["i"]), o)
                except (TypeError, ValueError):
                    pass
        if all((i + 1) in by_i for i in range(len(categories))):
            break
    if not by_i:
        # Zero parseable grades across all retries = systemic (bad creds / endpoint down /
        # wholly malformed), NOT genuine 0% coverage. Fail loud so a broken .env can't
        # silently score every trace 0.0. (A PARTIAL parse degrades gracefully below.)
        raise RuntimeError(
            f"coverage judge returned no parseable grades after {_MAX_RETRIES} attempts"
            + (f": {last_exc}" if last_exc else "")
        )
    result = []
    for i, cat in enumerate(categories):
        o = by_i.get(i + 1, {})
        result.append(
            {"category": cat, "covered": bool(o.get("covered", False)), "why": o.get("why", "")}
        )
    return result


def score(report: str, categories: list[str], client, model: str) -> dict:
    if not categories:
        return {"insights_recall": None, "n_required": 0, "n_covered": 0, "detail": []}
    detail = coverage(client, model, report, categories)
    n_cov = sum(1 for d in detail if d["covered"])
    return {
        "insights_recall": round(n_cov / len(categories), 3),
        "n_required": len(categories),
        "n_covered": n_cov,
        "detail": detail,
    }


# Per-trial cache file, alongside process.json / insight_grounding_llm.json.
CACHE_NAME = "insights_recall.json"
# Bump when the prompt or the scoring changes; every cache written by an older version is stale.
SCORER_VERSION = 2


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def inputs_key(report: str, cats: list[str], judge_model: str, base_url: str = "") -> dict:
    """The identity of THIS grading: scorer version, judge model, and a hash of the exact inputs
    (the report text plus the rubric categories it was scored against).

    Stamped into every payload and re-checked before a cache hit. `--model` and `--rubric` are both
    documented overrides, and without this key either one silently reuses the previous result —
    reporting numbers produced from different inputs with nothing in the output to reveal it.
    """
    return {
        "scorer_version": SCORER_VERSION,
        "judge_model": judge_model,
        # Same rationale as insight_grounding_llm.inputs_key — see the closed-set note there.
        # Must be load_env()'s resolved value, not os.environ — see the note in
        # insight_grounding_llm.inputs_key for why an os.environ fallback records "" forever.
        "judge_base_url": base_url,
        "prompts_sha": _sha(_COVERAGE_PROMPT),
        "inputs_sha256": _sha(report, "\x1f".join(cats)),
    }


def cached_ok(path: Path, expect: dict) -> bool:
    """True only if `path` holds a SUCCESSFUL prior grading OF THE SAME INPUTS.

    Rejects an `error` payload (must be retried, or a transient judge failure caches forever) and
    any key mismatch — different judge model, scorer version, rubric categories, or report bytes.
    A payload predating the key carries no `inputs_sha256` and is stale by construction, so it
    is re-graded once rather than trusted.
    """
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    if payload.get("error"):
        return False
    return all(payload.get(k) == v for k, v in expect.items())


def grade_one(report: str, cats: list[str], env: dict, model: str, expect: dict) -> dict:
    """Score ONE report from already-loaded text. Errors returned IN BAND so one bad trial cannot
    kill the pool, and so cached_ok() forces a retry rather than freezing the failure."""
    try:
        return {**expect, **score(report, cats, make_client(env), model)}
    except Exception as exc:  # noqa: BLE001 - in-band, see docstring
        return {**expect, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--traces", type=Path, default=HERE.parents[1] / "traces")
    ap.add_argument(
        "--rubric", type=Path, default=HERE.parents[1] / "gold" / "required_evidence.json"
    )
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--verbose", action="store_true", help="list per-category coverage")
    ap.add_argument(
        "--concurrency", type=int, default=12, help="reports graded in parallel (default 12)"
    )
    ap.add_argument(
        "--force", action="store_true", help=f"re-grade trials that already have {CACHE_NAME}"
    )
    args = ap.parse_args()

    rubric = load_rubric(args.rubric)
    env = load_env()
    model = (args.model or env.get("JUDGE_MODEL") or "openai/gpt-5.5").split("/")[-1]

    reports = sorted(args.traces.glob("*/*/*/report.md"))
    if args.limit:
        reports = reports[: args.limit]
    if not reports:
        sys.exit(f"no report.md under {args.traces}")

    # Resolve the rubric join BEFORE spending anything, so a missing rubric entry is a skip
    # rather than a wasted judge call, and partition against the cache.
    todo, cached, unjoined = [], [], []
    for rp in reports:
        scenario = slug_from_trial_dir(rp.parts[-3])
        cats = rubric.get(scenario, {}).get("categories") if scenario else None
        if not cats:
            unjoined.append((rp, scenario))
            continue
        (rp.parents[0]).mkdir(parents=True, exist_ok=True)
        report = rp.read_text()
        expect = inputs_key(report, cats, model, env.get("JUDGE_BASE_URL", ""))
        if cached_ok(rp.parents[0] / CACHE_NAME, expect) and not args.force:
            cached.append((rp, scenario, cats))
        else:
            todo.append((rp, scenario, cats, report, expect))
    for rp, scenario in unjoined:
        print(f"  ! {rp.parts[-3]}: no rubric entry (scenario {scenario!r})", file=sys.stderr)

    print(
        f"judge model: {model}   traces: {len(reports)}   to grade: {len(todo)}   "
        f"cached: {len(cached)}   unjoined: {len(unjoined)}\n"
    )
    print(f"{'run':30s} {'scenario':18s} {'recall':>6s} {'cov/req'}")
    recalls, dump = [], []

    def record(rp: Path, scenario: str, s: dict, from_cache: bool) -> None:
        if s.get("error"):
            print(f"  ! {rp.parts[-3]}: {s['error']}", file=sys.stderr)
            return
        run = rp.parts[-4]
        r = f"{s['insights_recall']:.2f}" if s.get("insights_recall") is not None else "  -"
        tag = " (cached)" if from_cache else ""
        print(f"  {run[:28]:28s} {scenario:18s} {r:>6s} {s['n_covered']}/{s['n_required']}{tag}")
        if args.verbose:
            for d in s.get("detail", []):
                print(f"      {'✓' if d['covered'] else '✗'} {d['category']}")
        if s.get("insights_recall") is not None:
            recalls.append(s["insights_recall"])
        dump.append({"run": run, "scenario": scenario, **s})

    if todo:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {
                ex.submit(grade_one, report, cats, env, model, expect): (rp, sc)
                for rp, sc, cats, report, expect in todo
            }
            for n, f in enumerate(as_completed(futs), 1):
                rp, scenario = futs[f]
                s = f.result()
                # Cache even on error: cached_ok() rejects it so the next run retries, but the
                # payload survives on disk for diagnosis.
                (rp.parents[0] / CACHE_NAME).write_text(json.dumps(s, indent=2))
                record(rp, scenario, s, from_cache=False)
                if n % 25 == 0:
                    print(f"    {n}/{len(todo)} graded", file=sys.stderr)

    for rp, scenario, _cats in cached:
        try:
            record(rp, scenario, json.loads((rp.parents[0] / CACHE_NAME).read_text()), True)
        except (OSError, ValueError):
            print(f"  ! {rp.parts[-3]}: unreadable cached {CACHE_NAME}", file=sys.stderr)

    if recalls:
        print(f"\nmean insights_recall over {len(recalls)} traces: {sum(recalls)/len(recalls):.3f}")
    if args.out:
        args.out.write_text(json.dumps(dump, indent=2) + "\n")
        print(f"wrote per-category coverage → {args.out}")
    # Found reports but scored none => every one failed the rubric join. Exit non-zero: a metric
    # may not report a headline number without its denominator, and a silent 0/N here reads as
    # "nothing to score" when it actually means the scenario key never matched.
    if not recalls:
        print(
            f"\n❌ scored 0 of {len(reports)} report(s) — none joined to {args.rubric.name}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
