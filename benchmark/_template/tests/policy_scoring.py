"""policy_scoring — score an agent report's policy/guideline citations.

Shared core, imported by BOTH:
  * the in-container Harbor verifier ``_template/tests/judge.py`` (per-trial reward.json), and
  * the offline CLI ``eval/metrics/grounding/policy_grounding.py`` (over trace dumps).

Stdlib only, except ``openai`` — imported lazily inside the LLM calls, so the deterministic
suite runs with no third-party deps. The LLM retry helpers below (``_call_judge`` /
``_extract_grade_array`` / ``_is_retryable``) mirror ``judge.py``'s own copies.

Policy grounding is scored SEPARATELY from patient-evidence grounding, along two axes — BOTH
graded as 3-class line items in ONE outcome rubric (the scenario's ``policy_rubrics.toml``),
not as standalone metrics:

  1. **Policy citation correctness** — do the citations resolve to a real corpus doc + valid line
     span (item ``kind = "citation_existence"``, graded DETERMINISTICALLY from the resolver), and
     does each cited passage factually back its claim (``kind = "citation_support"``, LLM-judged).
     The raw per-citation counts/rates are still emitted for transparency, but the SCORED form is
     the rubric.
  2. **Policy relevance** — does the agent ground its determination in the governing policy a
     domain expert expects (``kind = "relevance"``, graded DETERMINISTICALLY from gold-doc set
     membership): followed = cited only governing (gold) docs; partially_followed = also cited
     non-governing docs; did_not_follow = cited no governing doc. Whether a cited passage actually
     backs its claim is the separate ``citation_support`` item.

Each item is classified ``followed`` / ``partially_followed`` / ``did_not_follow`` (1.0 / 0.5 /
0.0); the policy outcome is the weighted mean of the item scores (items with nothing to check —
e.g. correctness when no citations were emitted — are graded not-applicable and excluded). On the
policy-OFF path the rubric is a fixed, deterministic abstention check (``followed`` = emitted no
citations; any citation ⇒ ``did_not_follow``). A single interpretable 3-class label per item is
steadier across judge models than a signed (−N…+N) weight sum.

Citation contract (see ``_template/instruction_policy.md``): inline
``[policy: <doc-filename> L<start>-L<end>]`` with the COMPLETE verbatim filename and
**physical 1-indexed** line numbers (including the ~5-line YAML frontmatter), resolving
against the same corpus ``.md`` file the verifier reads.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# 1. Citation parsing
# ─────────────────────────────────────────────────────────────────────────────

# A citation block is `[policy: ...]`. Models write more shapes inside it than the original
# single-span pattern accepted, and anything it did not match was DISCARDED SILENTLY rather than
# penalised — so a report citing nine documents could score zero citations. The loss is not
# uniform across models, so a narrow pattern turns policy grounding partly into a measure of
# citation-format compliance rather than of grounding. Shapes now accepted:
#
#   [policy: a.md L10-L20]                        canonical: one doc, one span
#   [policy: a.md L971, L4189, L4225-4231]        one doc, several spans
#   [policy: a.md L288-L292; policy: b.md L496]   several docs, `policy:` optionally repeated
#
# Still rejected, deliberately: a block with no line span at all. A citation that names a
# document but no lines cannot be resolved against source text, which is the whole point of the
# `L<start>-L<end>` contract, so counting it would inflate grounding rather than measure it.
#
# Doc is any run of non-space, non-`;` characters (filenames with spaces are not citeable, per
# the instruction/tool contract). End line optional (defaults to start). Case-insensitive.
_CITE_BLOCK_RX = re.compile(r"\[\s*policy:\s*(?P<body>[^\]]+?)\s*\]", re.IGNORECASE)
_SPAN_LIST = r"L\d+(?:\s*-\s*L?\d+)?(?:\s*,\s*L?\d+(?:\s*-\s*L?\d+)?)*"
_CITE_PART_RX = re.compile(
    rf"(?:policy:\s*)?(?P<doc>[^\s;]+)\s+(?P<spans>{_SPAN_LIST})", re.IGNORECASE
)
_SPAN_RX = re.compile(r"L?(?P<start>\d+)(?:\s*-\s*L?(?P<end>\d+))?", re.IGNORECASE)


@dataclass
class Citation:
    doc: str  # filename as written in the citation (verbatim)
    line_start: int
    line_end: int
    sentence: str  # the claim the citation is attached to
    raw: str  # the full [policy: ...] marker


def _claim_for(text: str, cite_start: int) -> str:
    """The sentence a citation supports: text from the previous sentence/line boundary up to
    the citation marker, markdown-stripped. Best-effort — enough to judge support against."""
    prefix = text[:cite_start]
    boundaries = list(re.finditer(r"[.!?;]\s|\n", prefix))
    start = boundaries[-1].end() if boundaries else 0
    claim = prefix[start:]
    # strip common markdown noise
    claim = re.sub(r"[*_`#>]+", "", claim)
    return claim.strip()


def parse_citations(report_md: str) -> list[Citation]:
    """Extract every ``[policy: <doc> L<a>-L<b>]`` citation and the claim it supports."""
    out: list[Citation] = []
    for block in _CITE_BLOCK_RX.finditer(report_md):
        # One Citation per (doc, span) so a multi-span or multi-doc block resolves each span
        # against source text independently, exactly as if it had been written out separately.
        for part in _CITE_PART_RX.finditer(block.group("body")):
            doc = part.group("doc").strip()
            for span in _SPAN_RX.finditer(part.group("spans")):
                start = int(span.group("start"))
                end = int(span.group("end")) if span.group("end") else start
                if end < start:
                    start, end = end, start
                out.append(
                    Citation(
                        doc=doc,
                        line_start=start,
                        line_end=end,
                        sentence=_claim_for(report_md, block.start()),
                        raw=block.group(0),
                    )
                )
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 2. Corpus resolution ("is this citation real?")
# ─────────────────────────────────────────────────────────────────────────────


def _corpus_files(corpus_dir: Path) -> dict[str, Path]:
    """Map {filename: path} for every corpus doc (cached per dir via lru is overkill here)."""
    return {p.name: p for p in Path(corpus_dir).glob("*.md")}


def resolve_doc(doc: str, corpus_dir: Path) -> Path | None:
    """Resolve a cited filename to a corpus path. Exact match, then +'.md', then
    case-insensitive — matching the instruction's 'exact verbatim filename' contract while
    tolerating a missing extension or case drift."""
    files = _corpus_files(corpus_dir)
    if doc in files:
        return files[doc]
    if not doc.lower().endswith(".md") and (doc + ".md") in files:
        return files[doc + ".md"]
    lower = {name.lower(): p for name, p in files.items()}
    for cand in (doc.lower(), doc.lower() + ".md"):
        if cand in lower:
            return lower[cand]
    return None


def resolve_citation(cit: Citation, corpus_dir: Path) -> dict:
    """{in_corpus, span_valid, cited_text, resolved_name}. Line numbers are physical
    1-indexed over the raw file (incl. frontmatter), per the citation contract."""
    path = resolve_doc(cit.doc, corpus_dir)
    if path is None:
        return {"in_corpus": False, "span_valid": False, "cited_text": None, "resolved_name": None}
    lines = path.read_text(errors="replace").splitlines()
    span_valid = 1 <= cit.line_start <= cit.line_end <= len(lines)
    cited_text = "\n".join(lines[cit.line_start - 1 : cit.line_end]) if span_valid else None
    return {
        "in_corpus": True,
        "span_valid": span_valid,
        "cited_text": cited_text,
        "resolved_name": path.name,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. File-level retrieval metrics (mirror evidence_retrieval_recall.score)
# ─────────────────────────────────────────────────────────────────────────────


def retrieval_metrics(gold_docs: set[str], cited_docs: set[str]) -> dict:
    """File-level precision/recall/F1 by set overlap. ``None`` when a component is
    undefined (no gold, or no citations), consistent with evidence_retrieval_recall."""
    hit = gold_docs & cited_docs
    recall = len(hit) / len(gold_docs) if gold_docs else None
    precision = len(hit) / len(cited_docs) if cited_docs else None
    if recall is None or precision is None:
        f1 = None
    elif recall + precision == 0:
        f1 = 0.0
    else:
        f1 = round(2 * precision * recall / (precision + recall), 3)
    return {
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "gold": sorted(gold_docs),
        "cited": sorted(cited_docs),
        "missed": sorted(gold_docs - cited_docs),
        "extra": sorted(cited_docs - gold_docs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. LLM helpers (canonical copy — judge.py imports these)
# ─────────────────────────────────────────────────────────────────────────────

_MAX_RETRIES = int(os.environ.get("JUDGE_MAX_RETRIES", "3"))
_RETRY_BASE_SEC = float(os.environ.get("JUDGE_RETRY_BASE_SEC", "2.0"))
_MAX_TOKENS = int(os.environ["JUDGE_MAX_TOKENS"]) if os.environ.get("JUDGE_MAX_TOKENS") else 0


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
    """Pull the largest clean list-of-dicts out of an LLM response (judges often prepend prose)."""
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
        raise ValueError(f"No JSON array of objects in LLM response: {text[:200]}")
    return best


def _call_judge(
    prompt: str,
    model: str,
    base_url: str,
    api_key: str,
    expected_n: int = 0,
    reasoning_effort: str | None = None,
) -> list[dict]:
    """Call an OpenAI-compatible LLM (the judge endpoint) with bounded retries. Returns the
    parsed JSON array; raises only after all retries fail."""
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key)
    # Mirror judge.py:_call_judge exactly: pass reasoning_effort when set, otherwise send NEITHER
    # it nor a temperature. The default JUDGE_MODEL (openai/gpt-5.5) is a reasoning model that
    # REJECTS temperature=0 ("only the default (1) is supported"), so we cannot pin it here — the
    # earlier `else {"temperature": 0}` 400'd on gpt-5.5 while judge.py (which sends {}) succeeded.
    # Reasoning models control determinism via reasoning_effort; plain chat models use their default.
    extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    if _MAX_TOKENS:
        extra["max_tokens"] = _MAX_TOKENS

    last_exc: BaseException | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **extra,
            )
            grades = _extract_grade_array(resp.choices[0].message.content or "")
            if expected_n and len(grades) < expected_n:
                raise ValueError(
                    f"judge returned {len(grades)} object(s) for {expected_n} expected "
                    f"(short/truncated response)"
                )
            return grades
        except BaseException as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= _MAX_RETRIES or not _is_retryable(exc):
                raise
            time.sleep(_RETRY_BASE_SEC * (2 ** (attempt - 1)))
    raise last_exc  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# 5. Optional LLM support check ("does the cited passage back the claim?")
# ─────────────────────────────────────────────────────────────────────────────

# creds dict: {"model", "base_url", "api_key", "reasoning_effort"?}. Absent/empty → support
# check skipped, deterministic metrics still computed.
Creds = dict


def _creds_from_env() -> Creds | None:
    """LLM judge creds from the environment — the same JUDGE_* vars judge.py uses and task.toml
    injects (JUDGE_MODEL is task-owned, default matches judge.py). Read from the environment for
    offline/dev use. Returns None (⇒ LLM passes skipped, deterministic evals still run) when a
    base URL or key is absent, so callers never assemble or pass creds themselves."""
    base = os.environ.get("JUDGE_BASE_URL")
    key = os.environ.get("JUDGE_API_KEY")
    if not (base and key):
        return None
    return {
        "base_url": base,
        "api_key": key,
        "model": os.environ.get("JUDGE_MODEL", "openai/gpt-5.5"),
        "reasoning_effort": os.environ.get("JUDGE_REASONING_EFFORT") or None,
    }


def _support_prompt(claim: str, cited_text: str) -> str:
    return f"""You are checking whether a cited policy/guideline passage FACTUALLY SUPPORTS a \
claim made in a clinical report. "Support" means the passage states, entails, or provides \
direct evidence for the claim — NOT merely that it is on the same topic.

## Claim (a sentence from the agent's report)
{claim}

## Cited policy passage (verbatim from the corpus, the exact lines the citation points to)
{cited_text}

Grade "met" if the passage supports the claim, "not met" if it does not (off-topic, \
contradictory, or too generic to substantiate the specific claim). Respond with a JSON array \
of exactly one object and nothing else:
[{{"justification": "one sentence on whether the passage backs the claim", "grade": "met" or "not met"}}]"""


# Cap items per batched support call. Same reason grounding_eval caps claims at 20: a long JSON
# array truncates mid-response and the later indices are silently lost. `expected_n` in
# _call_judge turns a short response into a retry rather than dropped verdicts.
_SUPPORT_BATCH = int(os.environ.get("POLICY_SUPPORT_BATCH", "10"))


def _support_prompt_batch(items: list[tuple[str, str]]) -> str:
    """One prompt covering N (claim, cited passage) pairs — the batched analogue of
    _support_prompt. Each pair is judged independently; the shared preamble is what saves the
    calls."""
    blocks = []
    for i, (claim, cited) in enumerate(items, 1):
        blocks.append(f"### Item {i}\nCLAIM: {claim}\n\nCITED PASSAGE:\n{cited}")
    body = "\n\n".join(blocks)
    return f"""You are checking whether each cited policy/guideline passage FACTUALLY SUPPORTS \
the claim it is attached to, in a clinical report. "Support" means the passage states, entails, \
or provides direct evidence for that claim — NOT merely that it is on the same topic.

Judge each item INDEPENDENTLY and on its own merits; do not let one item's verdict influence \
another's.

{body}

Grade each item "met" if its passage supports its claim, "not met" if it does not (off-topic, \
contradictory, or too generic to substantiate the specific claim). Respond with a JSON array of \
exactly {len(items)} objects and nothing else:
[{{"criterion": 1, "justification": "one sentence on whether the passage backs the claim", "grade": "met" or "not met"}}, ...]"""


def judge_support_batch(
    items: list[tuple[str, str]], creds: Creds, batch_size: int | None = None
) -> list[dict]:
    """Batched ``judge_support``: judge N (claim, cited_text) pairs in ceil(N/batch_size) calls
    instead of N. Returns a list parallel to ``items``.

    Semantics per item are the same as judge_support, but the VERDICTS ARE NOT GUARANTEED
    IDENTICAL — a judge seeing several pairs at once may grade differently from one seeing each
    alone. Validate agreement against the per-citation path before making this the default for a
    reported number.
    """
    size = batch_size or _SUPPORT_BATCH
    out: list[dict] = []
    for start in range(0, len(items), size):
        chunk = items[start : start + size]
        grades = _call_judge(
            _support_prompt_batch(chunk),
            creds["model"],
            creds["base_url"],
            creds["api_key"],
            expected_n=len(chunk),
            reasoning_effort=creds.get("reasoning_effort"),
        )
        for g in _align_by_criterion(grades, len(chunk)):
            out.append(
                {
                    "supported": (g.get("grade") or "").lower()
                    in ("met", "pass", "yes", "supported"),
                    "justification": g.get("justification", ""),
                }
            )
    return out


def judge_support(claim: str, cited_text: str, creds: Creds) -> dict:
    """{supported: bool, justification: str}. Requires LLM creds."""
    grades = _call_judge(
        _support_prompt(claim, cited_text),
        creds["model"],
        creds["base_url"],
        creds["api_key"],
        expected_n=1,
        reasoning_effort=creds.get("reasoning_effort"),
    )
    g = grades[0]
    return {
        "supported": (g.get("grade") or "").lower() in ("met", "pass", "yes", "supported"),
        "justification": g.get("justification", ""),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6. Condition-aware policy-relevance outcome rubric (3-class)
# ─────────────────────────────────────────────────────────────────────────────

# Each rubric item is classified into one of three classes; these map to a 0–1 score. One
# interpretable label per item is steadier across judge models than a signed MUST-DO/MUST-NOT sum.
_THREE_CLASS = {
    "followed": 1.0,
    "partially_followed": 0.5,
    "did_not_follow": 0.0,
}


def _label_score(label: str) -> float:
    """Map a 3-class label to its score, tolerating spacing/casing/hyphen drift
    ('Partially Followed' / 'did-not-follow' → the canonical key)."""
    key = re.sub(r"[\s\-]+", "_", (label or "").strip().lower())
    return _THREE_CLASS.get(key, 0.0)


def _parse_weight(w) -> float:
    """Magnitude of a signed weight string ('+2' → 2.0); default 1.0. Used to weight the mean."""
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", str(w or ""))
    return abs(float(m.group(1))) if m else 1.0


def _rate_to_class(n_ok: int, n_total: int) -> str | None:
    """3-class bucket for a proportion: all→followed, none→did_not_follow, some→partially_followed.
    None (not-applicable) when there is nothing to check (no citations)."""
    if n_total <= 0:
        return None
    if n_ok >= n_total:
        return "followed"
    if n_ok <= 0:
        return "did_not_follow"
    return "partially_followed"


def _relevance_class(valid_cited: set[str], gold: set[str]) -> str:
    """DETERMINISTIC 3-class policy relevance from gold-doc set membership:
      followed           — cited ≥1 governing (gold) doc AND only governing docs
      partially_followed — cited ≥1 governing doc BUT also cited non-governing (non-gold) doc(s)
      did_not_follow     — cited no governing doc (none, or only non-governing ones)
    ``valid_cited`` = docs whose citations resolve to a real corpus doc + valid span. Grading is
    deterministic (no LLM), so it is reproducible; whether a cited passage actually backs its claim
    is the separate ``citation_support`` item, and 'right topic / wrong authority' is handled by
    curating the gold set (``policy_gold.json``)."""
    if not (valid_cited & gold):
        return "did_not_follow"
    return "followed" if valid_cited <= gold else "partially_followed"


def _score_from_labels(graded: list[dict]) -> dict:
    """Overall policy score = weighted MEAN of the per-item 3-class scores (weight = |signed
    weight|, default 1), as a pct in [0, 100]. Items graded not-applicable (score None — nothing
    to check) are excluded so they neither help nor hurt. Mean (not sum) keeps the number
    comparable across scenarios with different item counts."""
    scored = [
        (g["score"], _parse_weight(g.get("weight"))) for g in graded if g.get("score") is not None
    ]
    if not scored:
        return {"earned": 0.0, "possible": 1.0, "pct": 0.0}
    mean = sum(s * w for s, w in scored) / sum(w for _, w in scored)
    return {"earned": round(mean, 3), "possible": 1.0, "pct": round(mean * 100, 1)}


def _item(rid, title, label, why, weight="+1"):
    """One graded rubric line. ``label`` None ⇒ not-applicable (score None; excluded from mean)."""
    return {
        "id": rid,
        "title": title,
        "weight": weight,
        "label": label or "not_applicable",
        "score": (_label_score(label) if label else None),
        "justification": why,
    }


def _align_by_criterion(grades: list[dict], n: int) -> list[dict]:
    """Order a judge response to rubric order by the 1-based ``criterion`` field, falling back
    to positional order. Robust to a judge returning criteria out of order (mirrors judge.py)."""
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


def grade_policy_outcome(
    policy_expected: bool,
    citations: list[Citation],
    resolved: list[dict],
    gold_docs: set[str],
    report: str,
    policy_rubrics: list[dict] | None,
    prompt: str,
    creds: Creds | None,
    support_results: list[dict | None] | None = None,
) -> dict | None:
    """Condition-aware 3-class policy outcome rubric. Returns {graded, score, mode} or None when
    the policy-on rubric can't be graded (no authored rubric or no LLM creds).

    policy_expected FALSE (policy-off, no corpus): a fixed, deterministic abstention check — the
    agent should emit NO policy citations. followed = none emitted; any citation ⇒ did_not_follow.

    policy_expected TRUE (corpus available): grade each authored ``policy_rubrics.toml`` item into
    followed / partially_followed / did_not_follow, dispatched by its ``kind``:
      * ``relevance`` (default) — DETERMINISTIC gold-doc set membership (no LLM).
      * ``citation_existence`` — DETERMINISTIC from the resolver (all/some/none citations resolve
        to a real doc + valid span).
      * ``citation_support`` — from the LLM support check (all/some/none cited passages back their
        claim); ``support_results`` must be supplied (parallel to ``citations``; None per entry
        for non-resolving citations).
    Score = weighted mean of the item scores over the items that could be scored. NO LLM creds are
    needed: relevance and citation_existence are deterministic, and citation_support is graded from
    ``support_results`` supplied by the caller (post-hoc, eval/metrics/policy_support.py).
    """
    total = len(citations)
    if not policy_expected:
        label = "followed" if total == 0 else "did_not_follow"
        why = (
            "no policy citations emitted (correct — none were available)"
            if total == 0
            else f"{total} policy citation(s) emitted despite no corpus available"
        )
        graded = [
            _item("P-OFF-1", "Emitted no policy citations when none were available", label, why)
        ]
        return {"graded": graded, "score": _score_from_labels(graded), "mode": "deterministic-off"}

    if not policy_rubrics:
        return None
    # Only the citation_support item invokes an LLM; relevance and citation_existence are
    # deterministic. A missing support result must NOT discard the whole rubric — returning None
    # whenever an LLM is unavailable throws away the relevance and existence scores too, which need
    # no LLM at all. Instead the support item is graded not-applicable (excluded from the weighted
    # mean, per _item) and the deterministic items still score. This is what makes the split work:
    # in-trial grades the deterministic items, eval/metrics/policy_support.py fills in support
    # afterwards and re-grades the rubric with it.
    # NOTE: do NOT synthesize an all-None support_results here. `support_results is None` means
    # "not judged" (the citation_support item is graded not-applicable and excluded from the mean);
    # a list of Nones means "judged, nothing supported" and scores did_not_follow. Conflating them
    # penalizes every trial for a check that simply hasn't run yet, turning a correct 100% into
    # 66.7% with no error.

    # Relevance is graded DETERMINISTICALLY: grounding is judged by gold-doc set membership, not an
    # LLM, so it is reproducible. valid_cited = docs whose citations resolve to a real corpus span.
    valid_cited = {
        _norm_doc(r["resolved_name"]) for r in resolved if r["in_corpus"] and r["span_valid"]
    }
    valid_cited.discard(None)
    gold_norm = {_norm_doc(d) for d in gold_docs}
    gold_norm.discard(None)

    n_valid = sum(1 for r in resolved if r["in_corpus"] and r["span_valid"])
    n_supported = sum(1 for s in (support_results or []) if s and s.get("supported"))

    graded: list[dict] = []
    for i, r in enumerate(policy_rubrics):
        kind = r.get("kind", "relevance")
        rid, title, weight = r.get("id", ""), r["title"], r.get("weight", "+1")
        if kind == "citation_existence":
            why = (
                f"{n_valid}/{total} citation(s) resolve to a real corpus doc + valid span"
                if total
                else "no policy citations to check"
            )
            graded.append(_item(rid, title, _rate_to_class(n_valid, total), why, weight))
        elif kind == "citation_support":
            if support_results is None:
                graded.append(
                    _item(
                        rid,
                        title,
                        None,
                        "support not judged in-trial — scored post-hoc by eval/metrics/policy_support.py",
                        weight,
                    )
                )
            else:
                why = (
                    f"{n_supported}/{total} cited passage(s) factually support their claim"
                    if total
                    else "no policy citations to check"
                )
                graded.append(_item(rid, title, _rate_to_class(n_supported, total), why, weight))
        else:  # relevance — DETERMINISTIC gold-doc membership (no LLM)
            n_hit = len(valid_cited & gold_norm)
            n_extra = len(valid_cited - gold_norm)
            why = (
                f"cited {n_hit} governing (gold) + {n_extra} non-governing doc(s)"
                if valid_cited
                else "no policy citations emitted"
            )
            graded.append(_item(rid, title, _relevance_class(valid_cited, gold_norm), why, weight))
    return {"graded": graded, "score": _score_from_labels(graded), "mode": "3class"}


# ─────────────────────────────────────────────────────────────────────────────
# 7. Orchestrator
# ─────────────────────────────────────────────────────────────────────────────


def _norm_doc(name: str | None) -> str | None:
    if not name:
        return None
    n = Path(name).name
    return n if n.lower().endswith(".md") else n + ".md"


def score_policy_grounding(
    report: str,
    corpus_dir: str | Path,
    gold_docs: set[str] | list[str],
    policy_expected: bool,
    policy_rubrics: list[dict] | None = None,
    prompt: str = "",
    run_support: bool | None = None,
) -> tuple[dict, dict]:
    """Score one report's policy grounding.

    Returns ``(reward, detail)``:
      * ``reward`` — flat dict of float|int for reward.json. Undefined rates / an ungradable
        outcome are OMITTED (not None) so the numeric contract holds; counts are always present.
      * ``detail`` — verbose sidecar (per-citation verdicts, missed/extra docs, graded items).

    LLM judge creds are read from the environment (JUDGE_*), like judge.py — callers
    do NOT pass them. Citation-correctness evals are always deterministic; the optional LLM
    support check runs only when creds exist AND ``run_support`` is true, which now defaults OFF
    (it is scored post-hoc); set POLICY_SUPPORT_CHECK=1 to force it
    in-trial. The policy-relevance OUTCOME rubric is LLM-judged
    from the scenario's authored ``policy_rubrics`` on the policy-on path (needs env creds), or a
    fixed deterministic abstention check on the policy-off path.
    """
    creds = _creds_from_env()
    if run_support is None:
        # Default OFF (step 4): the in-trial verifier is deterministic-only. Offline callers pass
        # run_support=True; set POLICY_SUPPORT_CHECK=1 to re-enable in-trial for a one-off.
        run_support = os.environ.get("POLICY_SUPPORT_CHECK", "0") != "0"
    corpus_dir = Path(corpus_dir)
    # Gold is only meaningful when policy is expected (policy-on). In the policy-off condition
    # there is nothing to retrieve, so file-level P/R/F1 are left undefined (the outcome rubric
    # instead checks that NO citations were emitted).
    gold_docs = {_norm_doc(d) for d in gold_docs} if policy_expected else set()
    gold_docs.discard(None)

    citations = parse_citations(report)
    resolved = [resolve_citation(c, corpus_dir) for c in citations]

    total = len(citations)
    n_valid = sum(1 for r in resolved if r["in_corpus"] and r["span_valid"])
    n_fabricated = total - n_valid
    in_corpus_docs = {
        _norm_doc(r["resolved_name"]) for r in resolved if r["in_corpus"] and r["span_valid"]
    }
    in_corpus_docs.discard(None)

    ret = retrieval_metrics(gold_docs, in_corpus_docs)

    have_creds = bool(creds and creds.get("base_url") and creds.get("api_key"))

    # LLM support check. This does NOT run in-trial:
    # citation support is the one policy component needing an LLM, it is billed per citation, and
    # it is scored afterwards by eval/metrics/policy_support.py (parity-closed on the -v3 runs).
    # The code path stays for the offline caller, which passes run_support=True explicitly.
    support_results: list[dict | None] | None = None
    support_rate = correct_rate = None
    if have_creds and run_support:
        support_results = []
        for c, r in zip(citations, resolved):
            if r["in_corpus"] and r["span_valid"]:
                support_results.append(judge_support(c.sentence, r["cited_text"], creds))
            else:
                support_results.append(None)
        judged = [s for s in support_results if s is not None]
        n_supported = sum(1 for s in judged if s.get("supported"))
        support_rate = (n_supported / len(judged)) if judged else None
        correct_rate = (n_supported / total) if total else None

    # policy outcome rubric — relevance + citation-correctness items (authored policy_rubrics,
    # LLM/deterministic-judged on policy-on; deterministic abstention on policy-off). None when
    # the on-path can't be graded.
    outcome = grade_policy_outcome(
        policy_expected,
        citations,
        resolved,
        gold_docs,
        report,
        policy_rubrics,
        prompt,
        creds,
        support_results=support_results,
    )

    # ── reward: counts always; rates / outcome only when defined (keeps float|int contract) ──
    n_items_scored = sum(
        1 for g in (outcome["graded"] if outcome else []) if g.get("score") is not None
    )
    reward: dict[str, float | int] = {
        "policy_expected": int(policy_expected),
        # policy_outcome_pct is a MEAN over the items that could be scored, so its denominator
        # changes when the citation_support item is not judged (it is scored post-hoc as of
        # the top-level README). Every scenario ships 3 equal-weight items, so an unjudged
        # support item raises the mean by up to 33.3 pts. Emit both so a consumer can tell a
        # deterministic-only number from a complete one instead of averaging them together.
        "policy_outcome_items_scored": n_items_scored,
        "policy_support_judged": int(support_results is not None),
        "policy_citations_total": total,
        "policy_citations_in_corpus": n_valid,
        "policy_citations_fabricated": n_fabricated,
        "policy_outcome_available": 1 if outcome is not None else 0,
    }
    if outcome is not None:
        reward["policy_outcome_earned"] = outcome["score"]["earned"]
        reward["policy_outcome_possible"] = outcome["score"]["possible"]
        # A policy-ON rubric with an unjudged citation_support item is a mean over FEWER items, so
        # it is not comparable with a complete one (3 equal-weight items -> up to 33.3 pts higher).
        # It therefore gets a DIFFERENT KEY rather than a flag beside the same key: flags get
        # ignored — metric.py and policy_grounding_summary.py both averaged this field blind — while
        # a distinct key makes mixing partial and complete values structurally impossible.
        # eval/metrics/policy_support.py --amend-reward promotes it once support is judged.
        incomplete = (
            policy_expected
            and support_results is None
            and any(r.get("kind") == "citation_support" for r in (policy_rubrics or []))
        )
        key = "policy_outcome_pct_deterministic" if incomplete else "policy_outcome_pct"
        reward[key] = outcome["score"]["pct"]
    if total:
        reward["policy_citation_resolve_rate"] = round(n_valid / total, 3)
    for key, val in (
        ("policy_file_precision", ret["precision"]),
        ("policy_file_recall", ret["recall"]),
        ("policy_file_f1", ret["f1"]),
        ("policy_citation_support_rate", support_rate),
        ("policy_citation_correct_rate", correct_rate),
    ):
        if val is not None:
            reward[key] = round(val, 3)

    detail: dict = {
        "policy_expected": policy_expected,
        "retrieval": ret,
        "citations": [
            {
                "raw": c.raw,
                "doc": c.doc,
                "lines": [c.line_start, c.line_end],
                "in_corpus": r["in_corpus"],
                "span_valid": r["span_valid"],
                "sentence": c.sentence[:400],
                "support": (support_results[i] if support_results else None),
            }
            for i, (c, r) in enumerate(zip(citations, resolved))
        ],
        "outcome_graded": outcome["graded"] if outcome else [],
        "outcome_score": outcome["score"] if outcome else None,
        # A single overall label when the rubric has one relevance statement (the common case);
        # None when it has several (see per-statement labels in outcome_graded).
        "outcome_label": (
            outcome["graded"][0]["label"] if outcome and len(outcome["graded"]) == 1 else None
        ),
        "outcome_mode": (
            outcome["mode"]
            if outcome
            else "unavailable (policy-on needs authored policy_rubrics + LLM creds)"
        ),
    }
    return reward, detail
