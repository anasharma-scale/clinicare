"""insight_grounding_llm — claim-level precision (P_claim in the paper): the LLM judge.

Tier 2 of insight_grounding (see insight_grounding.py for T1, the deterministic ID floor).
Adapted from DRBench's `factuality` to CliniCARE-Bench: break the report into atomic factual
claims and judge each against the evidence the agent actually retrieved.
DRBench source: github.com/ServiceNow/drbench
(`break_report_to_insights` + `get_factuality_verdict_multi`).

Two adaptations vs DRBench: (1) the *source resolver* — DRBench fetches a cited URL/file;
here the "source" is the MIMIC observation pool from the trace (evidence_pool, shared with
T1), so no live MIMIC and no gold set are needed. (2) the *prompts* below reuse DRBench's
two-step structure but are rewritten for this setting — DRBench's assume web/file citations
and generic report insights; ours target clinical claim types + entity/time attribution
against raw MIMIC rows. Not verbatim DRBench prompt text.

Why an LLM (vs T1's substring check): the discriminative grounding failures are numeric /
clinical claims — a lab value stated for the wrong patient or time, a finding the rows don't
support, a value that's close-but-wrong. A verbatim check can't catch "right number, wrong
entity" (the number substring-matches by chance) and can't read clinical context; the judge
is prompted to verify the value **and** its attribution (patient / time / measurement), not
mere presence.

  grounding = supported / n_claims     (per trial; a claim the retrieved evidence doesn't
                                         support is ungrounded whether it's actively wrong
                                         [contradicted] or simply absent [unverifiable])

Two LLM calls per report: (1) extract atomic claims, (2) judge them against the evidence
(batched; chunked + OR-aggregated when the pool exceeds the model context). Creds come from
the repo-root .env (JUDGE_BASE_URL / JUDGE_API_KEY);
JUDGE_MODEL / --model overrides the default.

  cd <repo root>
  python benchmark/eval/metrics/grounding/insight_grounding_llm.py \
      --traces benchmark/eval/traces --limit 3 --verbose
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from clinicare_core import load_env
from clinicare_core.paths import bootstrap

HERE = Path(__file__).resolve().parent

bootstrap(__file__, "eval", "grounding")
from insight_grounding import evidence_pool  # noqa: E402  (T1 shares the trace→pool loader)

ROOT = HERE.parents[3]  # repo root (grounding → metrics → eval → benchmark → root)
# Sized for a ~128k-token window (~500k chars), leaving headroom for the prompt + claims.
# Judges with a larger window are unaffected — a smaller chunk is always safe, it just costs
# an extra call. Don't raise this to match a specific model: chunk size changes which claims
# share context, so it is not result-neutral.
_CHUNK_CHARS = int(os.environ.get("IG_CHUNK_CHARS", "350000"))
_MAX_RETRIES = int(os.environ.get("IG_MAX_RETRIES", "3"))
_RETRY_BASE_SEC = float(os.environ.get("IG_RETRY_BASE_SEC", "2.0"))


def make_client(env: dict):
    from openai import OpenAI

    base, key = env.get("JUDGE_BASE_URL"), env.get("JUDGE_API_KEY")
    if not base or not key:
        sys.exit("JUDGE_BASE_URL / JUDGE_API_KEY not set (see .env.template).")
    return OpenAI(base_url=base, api_key=key)


def _call(client, model: str, prompt: str) -> str:
    last: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            return r.choices[0].message.content or ""
        # retry API/parse errors only; KeyboardInterrupt/SystemExit propagate immediately
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt >= _MAX_RETRIES:
                break
            time.sleep(_RETRY_BASE_SEC * (2 ** (attempt - 1)))
    raise last  # type: ignore[misc]


def _json_array(text: str) -> list:
    """Pull the first JSON array out of a model response (tolerates ```json fences / prose)."""
    text = re.sub(r"```(?:json)?|```", "", text)
    start = text.find("[")
    if start < 0:
        raise ValueError("no JSON array in response")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unbalanced JSON array in response")


# ── (1) claim extraction ───────────────────────────────────────────────────────────────────
_EXTRACT_PROMPT = """You are extracting atomic factual claims from a clinical decision report \
for grounding verification.

Extract every claim that asserts a SPECIFIC, checkable clinical or quantitative fact drawn \
from the patient's record: lab/vital values, medication names & doses, imaging/procedure \
findings, counts, dates of events, and presence/absence of a clinical event or order.

Rules:
- One atomic claim per item — split compound sentences.
- Keep the entity/context that makes it checkable (which patient/stay, what time, what test).
- EXCLUDE: the final verdict, restatements of the task criteria, methodology/reasoning \
sentences, and claims whose only content is a record ID (those are checked separately).
- Do NOT invent claims; only extract what the report states.

Return ONLY a JSON array of strings, e.g. ["Serum creatinine peaked at 2.3 mg/dL on 2180-09-20", ...].

REPORT:
{report}
"""


def extract_claims(client, model: str, report: str) -> list[str]:
    raw = _call(client, model, _EXTRACT_PROMPT.format(report=report))
    claims = [c.strip() for c in _json_array(raw) if isinstance(c, str) and c.strip()]
    return claims


# ── (2) judge claims against retrieved evidence ────────────────────────────────────────────
_JUDGE_PROMPT = """You are verifying whether clinical claims are grounded in the evidence a \
research agent actually retrieved from a patient's medical record.

EVIDENCE (raw rows/notes the agent retrieved from the database):
{evidence}

For EACH numbered claim, decide:
- "supported"   : the evidence contains this fact AND attributes it to the correct entity \
(patient/stay), time, and measurement. Be strict about qualifiers: if the claim specifies a \
time/window/status (e.g. "during the ICU stay", "in-window", "administered"), the evidence \
must show the fact under THAT qualifier. A value that appears but belongs to a different \
patient, a different time, an out-of-window event, or an order-vs-performed mismatch is NOT \
supported.
- "contradicted": the evidence directly conflicts with the claim (different value, or states \
the event did not occur / occurred outside the claimed window).
- "unverifiable": the evidence neither supports nor contradicts it (the fact is absent from \
what was retrieved, or the claim is a clinical judgment the rows can't confirm).

Judge ONLY against the evidence above — not your own medical knowledge.

CLAIMS:
{claims}

Return ONLY a JSON array, one object per claim IN ORDER:
[{{"i": 1, "verdict": "supported|contradicted|unverifiable", "reason": "<brief, cite the value/row>"}}, ...]
"""


def _judge_batch(client, model: str, claims: list[str], evidence: str) -> list[dict]:
    """Grade one small batch of claims against one evidence chunk. Retries if the response
    doesn't cover all indices (long arrays occasionally truncate / re-number) so a dropped
    index becomes a re-roll, not a silent 'no grade' that would deflate the score."""
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))
    prompt = _JUDGE_PROMPT.format(evidence=evidence, claims=numbered)
    best_by_i: dict[int, dict] = {}
    for _ in range(_MAX_RETRIES):
        try:
            out = _json_array(_call(client, model, prompt))
        except Exception:  # noqa: BLE001  (parse failure → re-roll)
            continue
        for o in out:
            if isinstance(o, dict) and "i" in o:
                try:
                    idx = int(o["i"])
                except (TypeError, ValueError):
                    continue
                # Canonicalize verdict case here so both the _RANK aggregation and score()
                # see lowercase — a judge "Supported" would otherwise rank 0 and score 0.
                if isinstance(o.get("verdict"), str):
                    o["verdict"] = o["verdict"].strip().lower()
                best_by_i.setdefault(idx, o)
        if all((i + 1) in best_by_i for i in range(len(claims))):
            break
    # None for indices the judge never returned (distinct from a real "unverifiable" grade),
    # so cross-chunk aggregation prefers any real grade over an omission.
    return [best_by_i.get(i + 1) for i in range(len(claims))]


def _chunks(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    n = (len(text) + size - 1) // size
    step = len(text) // n
    return [text[i * step : (i + 1) * step if i < n - 1 else len(text)] for i in range(n)]


# precedence when OR-aggregating a claim's verdict across evidence chunks: any chunk that
# supports wins; else any that contradicts; else unverifiable.
_RANK = {"supported": 2, "contradicted": 1, "unverifiable": 0}
# Cap claims per judge call — long JSON arrays truncate mid-response, dropping later indices.
_CLAIM_BATCH = int(os.environ.get("IG_CLAIM_BATCH", "20"))


def judge_claims(client, model: str, claims: list[str], evidence: str) -> list[dict]:
    if not claims:
        return []
    best: list[dict | None] = [None] * len(claims)
    # Each evidence chunk × each small claim-batch is one call; OR-aggregate across chunks
    # (a claim supported by any chunk is supported) so chunking never hides evidence.
    for part in _chunks(evidence, _CHUNK_CHARS):
        for b0 in range(0, len(claims), _CLAIM_BATCH):
            graded = _judge_batch(client, model, claims[b0 : b0 + _CLAIM_BATCH], part)
            for j, g in enumerate(graded):
                k = b0 + j
                if g is None:
                    continue
                if best[k] is None or _RANK.get(g.get("verdict", ""), 0) > _RANK.get(
                    best[k].get("verdict", ""), 0
                ):
                    best[k] = g
    return [b or {"verdict": "unverifiable", "reason": "ungraded (judge omitted)"} for b in best]


def score(claims: list[str], verdicts: list[dict]) -> dict:
    """grounding = supported / n_claims. Extraction restricts to *checkable record facts*, so
    a claim the retrieved evidence doesn't support is ungrounded regardless of whether it's
    actively wrong (contradicted) or simply absent (unverifiable) — both count against. The
    3-way breakdown is kept so a low score can be read (fabrication vs. under-retrieval)."""
    counts = {"supported": 0, "contradicted": 0, "unverifiable": 0}
    detail = []
    for c, v in zip(claims, verdicts):
        verd = v.get("verdict", "unverifiable").lower()  # canonical case (defensive)
        counts[verd] = counts.get(verd, 0) + 1
        detail.append({"claim": c, **v})
    grounding = counts["supported"] / len(claims) if claims else None
    return {"grounding": grounding, "n_claims": len(claims), **counts, "detail": detail}


# Per-trial cache file, alongside process.json / policy_support.json. Named for this metric so the
# two LLM grounding stages cannot clobber each other.
CACHE_NAME = "insight_grounding_llm.json"
# Bump when the prompts or the scoring change; every cache written by an older version is stale.
SCORER_VERSION = 2


def _sha(*parts: str) -> str:
    h = hashlib.sha256()
    for part in parts:
        h.update(part.encode("utf-8", "replace"))
        h.update(b"\0")
    return h.hexdigest()[:16]


def inputs_key(report: str, pool: str, judge_model: str, base_url: str = "") -> dict:
    """The identity of THIS grading: scorer version, judge model, and a hash of the exact inputs.

    Stamped into every payload and re-checked before a cache hit. Without it, `--judge-model` or an
    edited report/trajectory silently reuses the previous result — reporting and re-persisting
    numbers produced from different inputs, with nothing in the output to reveal it. That is the
    worst failure mode an eval cache can have, so the key is required, not advisory.
    """
    return {
        "scorer_version": SCORER_VERSION,
        "judge_model": judge_model,
        # Grading CONFIG, not just inputs. Both alter results, not merely throughput:
        #   _CHUNK_CHARS moves the evidence-chunk boundaries, and a fact split across a boundary
        #     can be unsupported in both halves even though OR-aggregation recovers most cases;
        #   _CLAIM_BATCH changes which claims share a judge prompt, and an LLM's verdict depends
        #     on the batch it is graded in.
        # Kept as explicit fields rather than folded into the hash so a stale cache says WHY.
        "chunk_chars": _CHUNK_CHARS,
        "claim_batch": _CLAIM_BATCH,
        # The endpoint, because the same model NAME can be a different deployment behind a
        # different proxy. Not a secret, so stored plainly.
        #
        # MUST be the value make_client() actually dialed, i.e. load_env()'s merged mapping —
        # NOT os.environ. load_env returns {**dotenv, **os.environ} without exporting, so a
        # JUDGE_BASE_URL set only in .env reaches the client but is ABSENT from os.environ. An
        # os.environ fallback here would record "" forever: a field that looks like coverage and
        # never invalidates. Callers pass it in; the default is only for direct unit calls.
        "judge_base_url": base_url,
        # The prompts themselves, hashed automatically. Previously these were covered only by a
        # MANUAL SCORER_VERSION bump — edit a prompt, forget to bump, and every cache stays valid
        # against changed grading logic. That is a likelier mistake than any of the above.
        "prompts_sha": _sha(_EXTRACT_PROMPT, _JUDGE_PROMPT),
        "inputs_sha256": _sha(report, pool),
    }


# DELIBERATELY NOT in the key, so the next review pass has an answer rather than a finding:
#   * JUDGE_API_KEY — rotating a key must not invalidate a cache, and "same URL, different key,
#     different deployment" is a routing detail judge_base_url already stands in for. Writing
#     secret-derived material into per-trial files on disk is not worth that corner.
#   * the OpenAI SDK / judge model's own version drift — unobservable from here; that is what
#     SCORER_VERSION and --force are for.
#   * temperature — hardcoded to 0 in _call, not configurable.
# The rule: cover everything reachable through a DOCUMENTED interface (CLI flag, .env.template
# var, env knob read by this module). Beyond that, --force.


def cached_ok(path: Path, expect: dict) -> bool:
    """True only if `path` holds a SUCCESSFUL prior grading OF THE SAME INPUTS.

    Two independent rejections:
      * an `error` payload (judge failure, bad model, expired key) — must be retried, or a
        transient failure caches permanently and every later run reports it forever;
      * a key mismatch — different judge model, different scorer version, or changed
        report/trajectory bytes. A payload predating the key carries no `inputs_sha256` and is
        therefore stale by construction, so it is re-graded once rather than trusted.
    """
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return False
    if payload.get("error"):
        return False
    return all(payload.get(k) == v for k, v in expect.items())


def load_inputs(tj: Path) -> tuple[str, str] | None:
    """(report_text, evidence_pool_text) for one trial, or None when the report is absent. Local
    reads only — no judge calls — which is what makes input-aware validation affordable for cached
    trials too."""
    report = tj.parents[1] / "verifier" / "report.md"
    if not report.exists():
        return None
    pool, _, _ = evidence_pool(tj.parent)
    return report.read_text(), pool


def grade_one(report: str, pool: str, env: dict, model: str, expect: dict) -> dict:
    """Score ONE trial from already-loaded inputs. Errors come back IN BAND rather than raising:
    one bad trial must not kill the pool, and `cached_ok` uses the `error` key to force a retry.

    A fresh client per trial — the OpenAI SDK object is cheap to build and this keeps the workers
    from sharing mutable state, matching how process.py hands base_url/api_key to each task.
    """
    try:
        client = make_client(env)
        claims = extract_claims(client, model, report)
        return {**expect, **score(claims, judge_claims(client, model, claims, pool))}
    except Exception as exc:  # noqa: BLE001 - in-band so the pool survives
        return {**expect, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--traces", type=Path, default=HERE.parents[1] / "traces")
    ap.add_argument(
        "--model", default=None, help="judge model (default JUDGE_MODEL or openai/gpt-5.5)"
    )
    ap.add_argument("--limit", type=int, default=0, help="cap number of trials (0 = all)")
    ap.add_argument("--out", type=Path, default=None, help="write per-claim verdicts JSON here")
    ap.add_argument("--verbose", action="store_true", help="print contradicted/unverifiable claims")
    ap.add_argument(
        "--concurrency", type=int, default=12, help="trials graded in parallel (default 12)"
    )
    ap.add_argument(
        "--force", action="store_true", help=f"re-grade trials that already have {CACHE_NAME}"
    )
    args = ap.parse_args()

    env = load_env()
    # Default matches every other judge call site, and is the model the published grounding
    # numbers were produced at — an unset JUDGE_MODEL must reproduce the paper, not diverge.
    model = args.model or env.get("JUDGE_MODEL") or "openai/gpt-5.5"
    # Provider routing prefixes (openai/…) aren't OpenAI-SDK model
    # names; strip to the bare model when calling the proxy through the OpenAI SDK.
    model = model.split("/")[-1]

    trials = sorted(args.traces.glob("*/*/*/trajectory.json"))
    if args.limit:
        trials = trials[: args.limit]
    if not trials:
        sys.exit(f"no trajectories under {args.traces}")

    # Partition before spending anything: a re-run must cost only the trials that are missing or
    # previously errored, and must still report the JOB-WIDE mean by folding the cache back in.
    todo, cached, noreport = [], [], []
    for tj in trials:
        (tj.parents[1] / "verifier").mkdir(parents=True, exist_ok=True)
        loaded = load_inputs(tj)
        if loaded is None:
            noreport.append(tj)
            continue
        report, pool = loaded
        expect = inputs_key(report, pool, model, env.get("JUDGE_BASE_URL", ""))
        if cached_ok(tj.parents[1] / "verifier" / CACHE_NAME, expect) and not args.force:
            cached.append(tj)
        else:
            todo.append((tj, report, pool, expect))
    for tj in noreport:
        print(f"  ! {tj.parts[-3]}: no verifier/report.md", file=sys.stderr)

    print(
        f"judge model: {model}   trials: {len(trials)}   to grade: {len(todo)}   cached: {len(cached)}\n"
    )
    print(f"{'run':30s} {'scenario':18s} {'grounded':>8s} {'sup':>4s} {'con':>4s} {'unv':>4s}")
    rows, rates, dump = [], [], []

    def record(tj: Path, s: dict, from_cache: bool) -> None:
        run, slug = tj.parts[-4], tj.parts[-3]
        if s.get("error"):
            print(f"  ! {slug}: {s['error']}", file=sys.stderr)
            return
        g = f"{s['grounding']:.2f}" if s.get("grounding") is not None else "  -"
        tag = " (cached)" if from_cache else ""
        print(
            f"  {run[:28]:28s} {slug:18s} {g:>8s} {s['supported']:>4d} "
            f"{s['contradicted']:>4d} {s['unverifiable']:>4d}{tag}"
        )
        if args.verbose:
            for d in s.get("detail", []):
                if d.get("verdict") != "supported":
                    print(f"      [{d.get('verdict')}] {d['claim']}  — {d.get('reason','')[:120]}")
        if s.get("grounding") is not None:
            rates.append(s["grounding"])
        rows.append((run, slug, s))
        dump.append({"run": run, "scenario": slug, **s})

    if todo:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {
                ex.submit(grade_one, report, pool, env, model, expect): tj
                for tj, report, pool, expect in todo
            }
            for n, f in enumerate(as_completed(futs), 1):
                tj = futs[f]
                s = f.result()
                # Write the cache even on error: cached_ok() rejects it, so the next run retries,
                # but the payload is on disk for diagnosis instead of only in a lost stdout.
                (tj.parents[1] / "verifier" / CACHE_NAME).write_text(json.dumps(s, indent=2))
                record(tj, s, from_cache=False)
                if n % 25 == 0:
                    print(f"    {n}/{len(todo)} graded", file=sys.stderr)

    # Cached trials count toward the mean, so a re-run reports the same job-wide number rather
    # than only what it happened to grade this time.
    for tj in cached:
        try:
            record(tj, json.loads((tj.parents[1] / "verifier" / CACHE_NAME).read_text()), True)
        except (OSError, ValueError):
            print(f"  ! {tj.parts[-3]}: unreadable cached {CACHE_NAME}", file=sys.stderr)

    if rates:
        print(f"\nmean grounding over {len(rates)} trials: {sum(rates)/len(rates):.3f}")
    if args.out:
        args.out.write_text(json.dumps(dump, indent=2) + "\n")
        print(f"wrote per-claim verdicts → {args.out}")

    # Found inputs but scored none => every one failed to join (missing report, no gold match).
    # Exit non-zero rather than printing an empty table and exiting 0: a silent 0/N reads as
    # "nothing to score" when it means the join is broken.
    if not rates:
        print(
            f"\n❌ scored 0 of {len(trials)} trace(s) — nothing joined",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
