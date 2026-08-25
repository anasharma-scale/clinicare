"""The LLM-judged process-rubric core — prompt, judge call, and scoring.

Imported by ``eval/metrics/process.py`` (the per-trial grade) and
``eval/reliability/judge_panel.py`` (the multi-judge agreement study).

The prompt is the metric. ``process_pct`` is defined by the exact text below, so an edit here
changes what the number means — treat it like a schema change, not a wording tweak.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path


def _parse_weight(w: str) -> int:
    m = re.search(r"([+-]\d+)", w or "")
    return int(m.group(1)) if m else 0


def _build_reference(bundle: dict) -> str:
    """Assemble the grader's reference: the operationalized spec + correct label."""
    parts: list[str] = []
    if bundle.get("clinical_question"):
        parts.append(f"Clinical question: {bundle['clinical_question'].strip()}")
    if bundle.get("reference_spec"):
        parts.append(bundle["reference_spec"].strip())
    label = (bundle.get("ground_truth_label") or "").strip()
    if label:
        parts.append(
            f"Correct answer for this case (silver label): {label}. "
            "Use this only to grade the 'returned the correct label' criterion — do NOT reward "
            "an agent for a right label reached by wrong methodology, and grade every other "
            "criterion on its own terms."
        )
    return "\n\n".join(parts) if parts else "(no reference spec bundled)"


def _build_judge_prompt(prompt: str, reference: str, agent_work: str, rubrics: list[dict]) -> str:
    criteria_lines = []
    for i, r in enumerate(rubrics):
        criteria_lines.append(f"{i + 1}. [{r['weight']}] {r['title']}")
    criteria_text = "\n".join(criteria_lines)

    return f"""You are grading the PROCESS (methodology and execution) of an AI agent that \
worked a clinical deep-research task over the MIMIC-IV dataset. The agent reached its \
answer by calling read-only MIMIC tools and then writing a report; you are given the \
report and the tool-call trajectory.

## Task prompt (what the agent was asked)
{prompt}

## Reference specification (the definitive standard for this case)
{reference}

## Agent's work (report.md, then the tool-call trajectory)
{agent_work}

## Rubric criteria
Each criterion is a statement about what the agent did. The bracketed number is its \
weight and is NOT your concern — grade only whether the statement is TRUE of the agent's \
work.
{criteria_text}

## Grading instructions
- Grade each criterion LITERALLY: "met" means the described behavior/fact IS TRUE / IS \
PRESENT in the agent's work; "not met" means it IS NOT. Do NOT consider whether the \
behavior is good or bad — some criteria describe mistakes.
- Base your grade on evidence in the report AND the trajectory. A methodology claim in \
the report only counts as "met" if it is consistent with the trajectory; if the \
trajectory shows the agent did something different from what the report claims, grade \
by what it actually did.
- For a "did NOT do X" style MUST-NOT criterion, "met" means the agent DID commit that \
error. Only grade it "met" with concrete evidence of the error; if the error is absent, \
grade "not met".
- Ignore surface formatting, whitespace, and phrasing. Focus on substance.
- For the "correct label" criterion, compare the agent's top-line verdict against the \
reference label above.

For each criterion, first reason briefly about whether the statement is true, then give \
your grade. Respond with a JSON array and nothing else:
[
  {{"criterion": 1, "justification": "brief reasoning about whether the statement is true", "grade": "met" or "not met"}},
  ...
]"""


_MAX_RETRIES = int(os.environ.get("JUDGE_MAX_RETRIES", "3"))

_RETRY_BASE_SEC = float(os.environ.get("JUDGE_RETRY_BASE_SEC", "2.0"))

# Output-token cap for the judge call. Left unset by default so each model uses its API
# default (matches how gpt-5.x was graded). Set JUDGE_MAX_TOKENS to give verbose reasoning
# models enough room that reasoning doesn't starve the JSON answer (empty/truncated response).
_MAX_TOKENS = int(os.environ["JUDGE_MAX_TOKENS"]) if os.environ.get("JUDGE_MAX_TOKENS") else 0

# When agent_work exceeds _CHUNK_THRESHOLD_CHARS, grade it in sequential chunks
# and OR-aggregate the per-criterion grades. The report leads the text so it lands
# in chunk 1; only a long trajectory tail spills into later chunks.
_CHUNK_THRESHOLD_CHARS = int(os.environ.get("JUDGE_CHUNK_THRESHOLD_CHARS", "500000"))

_CHUNK_TARGET_CHARS = int(os.environ.get("JUDGE_CHUNK_TARGET_CHARS", "300000"))


def _is_retryable(exc: BaseException) -> bool:
    """Network/rate/5xx errors and JSON-parse failures are retryable; auth/bad-request are not."""
    cls = type(exc).__name__
    if cls in {
        "APIConnectionError",
        "APITimeoutError",
        "RateLimitError",
        "InternalServerError",
        "APIStatusError",
    }:
        return True
    if isinstance(exc, (json.JSONDecodeError, ValueError, TimeoutError, ConnectionError)):
        return True
    return False


def _extract_grade_array(text: str) -> list[dict]:
    """Pull the largest clean list-of-dicts out of the judge's response.

    Judges often prepend prose (possibly containing stray brackets), so we scan
    every ``[`` and take the largest array that parses via ``raw_decode``.
    """
    decoder = json.JSONDecoder()
    best: list[dict] | None = None
    for m in re.finditer(r"\[", text):
        try:
            obj, _ = decoder.raw_decode(text, m.start())
        except json.JSONDecodeError:
            tail = text[m.start() :]
            fixed = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", tail)
            fixed = re.sub(r"[\x00-\x1f]", " ", fixed)
            try:
                obj, _ = decoder.raw_decode(fixed, 0)
            except json.JSONDecodeError:
                continue
        if not isinstance(obj, list) or not obj or not all(isinstance(x, dict) for x in obj):
            continue
        if best is None or len(obj) > len(best):
            best = obj
    if best is None:
        raise ValueError(f"No JSON array of grade objects in judge response: {text[:200]}")
    return best


def _call_judge(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    expected_n: int = 0,
    reasoning_effort: str | None = None,
) -> list[dict]:
    """Call the LLM judge with bounded retries. Raises only after all retries fail.

    `reasoning_effort` (e.g. 'high'/'xhigh') is passed through to the API when set — for
    reasoning models; omitted otherwise so non-reasoning models aren't sent an unknown param."""
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    if _MAX_TOKENS:
        extra["max_tokens"] = _MAX_TOKENS

    last_exc: BaseException | None = None
    last_raw_text: str = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **extra,
            )
            last_raw_text = resp.choices[0].message.content or ""
            grades = _extract_grade_array(last_raw_text)
            if expected_n and len(grades) < expected_n:
                raise ValueError(
                    f"judge returned {len(grades)} grade(s) for {expected_n} criteria "
                    f"(short/truncated response)"
                )
            return grades
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= _MAX_RETRIES or not _is_retryable(exc):
                if last_raw_text and isinstance(exc, (ValueError, json.JSONDecodeError)):
                    dump = (
                        Path(os.environ.get("JUDGE_RAW_DUMP_DIR", "/logs/verifier"))
                        / "judge_raw_response.txt"
                    )
                    try:
                        dump.parent.mkdir(parents=True, exist_ok=True)
                        dump.write_text(last_raw_text)
                        print(f"[judge] dumped raw response to {dump}", file=sys.stderr)
                    except OSError:
                        pass
                raise
            wait = _RETRY_BASE_SEC * (2 ** (attempt - 1))
            print(
                f"[judge] {type(exc).__name__} on attempt {attempt}/{_MAX_RETRIES}: "
                f"{str(exc)[:140]} — retrying in {wait:.1f}s",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]


def _chunk_text(text: str, target_chars: int) -> list[str]:
    """Split text into ~target_chars chunks at paragraph/line boundaries."""
    if len(text) <= target_chars:
        return [text]
    n_chunks = (len(text) + target_chars - 1) // target_chars
    base = len(text) // n_chunks
    chunks: list[str] = []
    pos = 0
    for _ in range(n_chunks - 1):
        end = pos + base
        window = min(end + 5000, len(text))
        nl = text.find("\n\n", end, window)
        if nl == -1:
            nl = text.find("\n", end, window)
        if nl == -1 or nl <= pos:
            nl = end
        chunks.append(text[pos:nl])
        pos = nl
    chunks.append(text[pos:])
    return chunks


def _align_by_criterion(grades: list[dict], n: int) -> list[dict]:
    """Order a judge response to rubric order: index i -> the grade whose 1-based
    ``criterion`` field is i+1, falling back to positional order when that field is
    absent. Robust to a judge that returns criteria out of order. Missing entries
    become ``{}`` so callers can treat them as "no grade for this criterion"."""
    by_idx: dict[int, dict] = {}
    for g in grades:
        c = g.get("criterion")
        if isinstance(c, int) and 1 <= c <= n and c not in by_idx:
            by_idx[c] = g
    out: list[dict] = []
    for i in range(n):
        g = by_idx.get(i + 1)
        if g is None:
            g = grades[i] if i < len(grades) else {}
        out.append(g)
    return out


def _aggregate_chunked_grades(
    per_chunk_grades: list[list[dict]], rubrics: list[dict]
) -> list[dict]:
    """OR-aggregate: a criterion is 'met' overall if ANY chunk graded it met."""
    n = len(rubrics)
    # Align each chunk's grades by the judge's `criterion` field before indexing by
    # rubric position — a chunk can return its grades out of order, and a positional
    # read would then score criteria against the wrong rubric item (silently).
    per_chunk_aligned = [_align_by_criterion(cg, n) for cg in per_chunk_grades]
    aggregated: list[dict] = []
    for i, r in enumerate(rubrics):
        met_justifications: list[str] = []
        any_met = False
        seen_chunks = 0
        for chunk_idx, aligned in enumerate(per_chunk_aligned):
            g = aligned[i]
            if not g:  # this chunk produced no grade for this criterion
                continue
            seen_chunks += 1
            grade_str = (g.get("grade") or "").lower()
            if grade_str in ("met", "pass"):
                any_met = True
                just = g.get("justification", "")
                if just:
                    met_justifications.append(f"[chunk {chunk_idx + 1}] {just}")
        if any_met:
            grade = "met"
            justification = " ".join(met_justifications) or "Observed in agent work."
        elif seen_chunks == 0:
            grade = "error"
            justification = "No chunk produced a grade for this criterion."
        else:
            grade = "not met"
            justification = f"Not observed across {seen_chunks} chunks."
        aggregated.append(
            {
                "criterion_idx": i,
                "id": r.get("id", ""),
                "title": r["title"],
                "weight": r["weight"],
                "grade": grade,
                "justification": justification,
            }
        )
    return aggregated


def _compute_score(graded: list[dict]) -> dict:
    """Sum met credit minus met penalties over the achievable positive total.

    ``possible`` is the sum of positive weights only (the MUST-DOs). Penalties
    (met MUST-NOTs) subtract from ``earned``; the percentage is floored at 0.
    """
    earned = possible = 0.0
    for g in graded:
        w = _parse_weight(g.get("weight", ""))
        met = g.get("grade", "").lower() in ("met", "pass")
        if w > 0:
            possible += w
            if met:
                earned += w
        elif w < 0:
            if met:
                earned += w  # penalty
    pct = max(0.0, (earned / possible * 100) if possible > 0 else 0.0)
    return {"earned": round(earned, 1), "possible": round(possible, 1), "pct": round(pct, 1)}


def _grade(
    rubrics: list[dict],
    prompt: str,
    reference: str,
    agent_work: str,
    model: str,
    base_url: str,
    api_key: str,
    reasoning_effort: str | None = None,
) -> dict:
    if not rubrics or not agent_work:
        return {
            "graded": [],
            "score": {"earned": 0.0, "possible": 0.0, "pct": 0.0},
            "skipped_reason": "no rubrics" if not rubrics else "no agent work",
        }

    if len(agent_work) > _CHUNK_THRESHOLD_CHARS:
        chunks = _chunk_text(agent_work, _CHUNK_TARGET_CHARS)
        per_chunk_grades: list[list[dict]] = []
        chunk_errors: list[dict] = []
        for idx, chunk in enumerate(chunks):
            chunk_note = (
                f"NOTE: The agent's work is too large to grade in a single pass. This is "
                f"chunk {idx + 1} of {len(chunks)}. Grade each criterion based ONLY on what "
                f"you observe in THIS chunk; results are OR-aggregated across chunks (a "
                f"criterion is 'met' overall if any chunk grades it 'met'). If a behavior is "
                f"not visible here, mark 'not met' — the evidence may appear in another "
                f"chunk.\n\n"
            )
            judge_prompt = chunk_note + _build_judge_prompt(prompt, reference, chunk, rubrics)
            try:
                per_chunk_grades.append(
                    _call_judge(
                        judge_prompt,
                        model,
                        base_url,
                        api_key,
                        expected_n=len(rubrics),
                        reasoning_effort=reasoning_effort,
                    )
                )
            except BaseException as exc:  # noqa: BLE001
                chunk_errors.append(
                    {"chunk": idx, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                )
                print(f"[judge] chunk {idx + 1}/{len(chunks)} FAILED: {exc}", file=sys.stderr)
        if not per_chunk_grades:
            raise RuntimeError(f"All {len(chunks)} chunks failed during grading: {chunk_errors}")
        graded = _aggregate_chunked_grades(per_chunk_grades, rubrics)
        return {
            "graded": graded,
            "score": _compute_score(graded),
            "chunk_info": {
                "n_chunks": len(chunks),
                "n_succeeded": len(per_chunk_grades),
                "agent_work_chars": len(agent_work),
                "errors": chunk_errors,
            },
        }

    judge_prompt = _build_judge_prompt(prompt, reference, agent_work, rubrics)
    grades_raw = _call_judge(
        judge_prompt,
        model,
        base_url,
        api_key,
        expected_n=len(rubrics),
        reasoning_effort=reasoning_effort,
    )
    aligned = _align_by_criterion(grades_raw, len(rubrics))
    graded = []
    for i, r in enumerate(rubrics):
        g = aligned[i]
        graded.append(
            {
                "criterion_idx": i,
                "id": r.get("id", ""),
                "title": r["title"],
                "weight": r["weight"],
                "grade": g.get("grade", "error"),
                "justification": g.get("justification", ""),
            }
        )
    return {"graded": graded, "score": _compute_score(graded)}
