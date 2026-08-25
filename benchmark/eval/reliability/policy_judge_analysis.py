"""Phase 2 of the POLICY judge-panel study: from the per-(trajectory, judge, rep) grades emitted
by policy_judge_panel.py, compute the reliability / agreement / bias metrics and write a report.

The policy analogue of ``judge_analysis.py``. That script assumes a **boolean** met/not-met grade;
the policy outcome rubric is **3-class** (``followed`` / ``partially_followed`` / ``did_not_follow``
→ ``1.0`` / ``0.5`` / ``0.0``), so the metrics are generalized:

  * **rep_noise** is the actual population variance of the score across a judge's reps
    (``Var_r(g)``), not the Bernoulli plug-in ``p̂(1−p̂)`` — correct for a 3-valued score.
  * **fleiss_k / disagree_dc** are computed over the **3 label categories** (each judge's
    rep-collapsed verdict = the class nearest its mean score), not 2.
  * the **aggregate score** is the rubric's weighted **mean** (``a_c = 100·w_c/Σw``), not the
    process rubric's signed ``+N/possible`` sum.

Items graded **not-applicable** (score ``None`` — nothing to check, e.g. citation correctness when
the agent emitted no citations) are excluded per-trajectory, exactly as the scorer excludes them
from the mean. Unit of analysis is (scenario, item); trajectories are pooled within a scenario.

  python benchmark/eval/reliability/policy_judge_analysis.py --in jobs/policy_judge_panel.jsonl \
      --job claude=jobs/policy_on_XXXX \
      --out jobs/policy_judge_panel_report.md --cov-out jobs/policy_judge_panel_cov.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

_DEFAULT_SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "_scenarios"

# 3-class score scale (matches policy_scoring._THREE_CLASS).
_CLASSES = ("did_not_follow", "partially_followed", "followed")  # index = category, score = idx/2
_SCORES = (0.0, 0.5, 1.0)


# ── tiny stats helpers (self-contained; do not import the boolean judge_analysis) ──
def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _pvar(xs: list[float]) -> float:  # population variance
    if not xs:
        return 0.0
    m = _mean(xs)
    return _mean([(x - m) ** 2 for x in xs])


def _pcov(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or not xs:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    return _mean([(x - mx) * (y - my) for x, y in zip(xs, ys)])


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    vx, vy = _pvar(xs), _pvar(ys)
    if vx <= 1e-12 or vy <= 1e-12:
        return None
    return _pcov(xs, ys) / (vx**0.5 * vy**0.5)


def _wabs(w) -> float:
    """Magnitude of a signed weight string ('+2'→2.0, '-1'→1.0); default 1.0 (matches
    policy_scoring._parse_weight)."""
    m = re.search(r"([+-]?\d+(?:\.\d+)?)", str(w or ""))
    return abs(float(m.group(1))) if m else 1.0


def _nearest_class(pbar: float) -> int:
    """The 3-class category (0/1/2) whose score is nearest a rep-averaged score — a judge's
    rep-collapsed verdict, monotone with the score (reduces to a majority vote for 2 classes)."""
    return min(range(3), key=lambda c: abs(_SCORES[c] - pbar))


def _judge_family(model: str) -> str:
    m = model.lower()
    if "gpt" in m or "openai" in m:
        return "gpt"
    if "claude" in m or "sonnet" in m or "haiku" in m or "opus" in m:
        return "claude"
    if "gemini" in m:
        return "gemini"
    return "other"


def _fleiss_kappa(ratings_per_subject: list[list[int]], n_cats: int) -> float | None:
    """Fleiss' kappa over ``n_cats`` categories. ratings_per_subject: for each subject
    (trajectory), one category index per rater (judge). Same rater count per subject required;
    subjects with fewer are dropped."""
    n_raters = max((len(r) for r in ratings_per_subject), default=0)
    subj = [r for r in ratings_per_subject if len(r) == n_raters]
    if n_raters < 2 or len(subj) < 2:
        return None
    cats = list(range(n_cats))
    p_j = {c: 0 for c in cats}
    p_bar_terms = []
    for r in subj:
        counts = {c: r.count(c) for c in cats}
        for c in cats:
            p_j[c] += counts[c]
        pi = (sum(counts[c] ** 2 for c in cats) - n_raters) / (n_raters * (n_raters - 1))
        p_bar_terms.append(pi)
    total = len(subj) * n_raters
    pj = {c: p_j[c] / total for c in cats}
    p_bar = _mean(p_bar_terms)
    p_e = sum(v**2 for v in pj.values())
    if abs(1 - p_e) < 1e-12:
        return 1.0  # degenerate: everyone always the same category
    return (p_bar - p_e) / (1 - p_e)


def _load_rubric_defs(scenarios_dir: Path) -> dict[str, dict[str, dict]]:
    """{scenario_id: {item_id: {title, weight, kind}}} from _scenarios/*/policy_rubrics.toml, so the
    report can say what each item measures. Degrades to {} if the dir is absent."""
    defs: dict[str, dict[str, dict]] = {}
    if not scenarios_dir.is_dir():
        return defs
    for d in sorted(scenarios_dir.glob("scenario-*")):
        scenario_toml, rub_toml = d / "scenario.toml", d / "policy_rubrics.toml"
        if not (scenario_toml.is_file() and rub_toml.is_file()):
            continue
        try:
            cid = tomllib.loads(scenario_toml.read_text())["id"]
            rubrics = tomllib.loads(rub_toml.read_text()).get("rubric", [])
        except (ValueError, KeyError):
            continue
        defs[cid] = {
            r["id"]: {
                "title": r.get("title", ""),
                "weight": r.get("weight", ""),
                "kind": r.get("kind", "relevance"),
            }
            for r in rubrics
            if "id" in r
        }
    return defs


def _load_outcomes(job_dirs: list[tuple[str, Path]]) -> dict[tuple[str, str], int]:
    """{(agent_family, task_id): outcome_correct} from each trial's verifier/reward.json — the
    deterministic primary reward, for the corr_out column (does grounding predict a right answer?).
    """
    out: dict[tuple[str, str], int] = {}
    for fam, jd in job_dirs:
        for trial in jd.glob("*__*"):
            rj = trial / "verifier" / "reward.json"
            if not rj.is_file():
                continue
            try:
                oc = json.loads(rj.read_text()).get("outcome_correct")
            except ValueError:
                continue
            if oc is not None:
                out[(fam, trial.name.rsplit("__", 1)[0])] = int(oc)
    return out


def load(path: str) -> list[dict]:
    return [json.loads(ln) for ln in Path(path).read_text().splitlines() if ln.strip()]


_METHODS = r"""
## How to read this report

**What we did.** Each *trajectory* (one agent rollout of one policy-ON task) is graded by every
*judge model*, R times ("reps"), on each *item* of that scenario's policy outcome rubric. A grade is
**3-class**: `g ∈ {0, ½, 1}` for did_not_follow / partially_followed / followed. Items with
nothing to check (e.g. citation correctness when no citations were emitted) are *not-applicable*
(score `None`) and excluded — exactly as the scorer excludes them from the weighted mean. Analysis
is **per (scenario, item)**: we pool over trajectories within a scenario, never across items.

**Notation.** For a fixed item, `g(j,t,r) ∈ {0, ½, 1}` is judge `j`'s grade of trajectory `t` on
rep `r`; `p̂(j,t) = mean_r g(j,t,r)` is the rep-averaged score, and `Var` is the population variance.

**Metrics (per item):**
- **meanScore** — mean of `p̂(j,t)` over judges/trajectories (0–1). How followed the item is on average.
- **rep_noise** — judge stochasticity (**lower = better**): `mean over (j,t) of Var_r(g(j,t,r))`.
  How much one judge's score moves across its *own* reps on the same trajectory (0 = identical every rep).
- **between_traj** — discrimination (**higher = better**): `mean_j of Var_t(p̂(j,t))`.
  How much the item separates *different* trajectories; ≈0 = uninformative.
- **between_judge** — cross-judge spread: `mean_t of Var_j(p̂(j,t))`. How much judges differ on the same trajectory.
- **disagree_dc** — mean pairwise disagreement of the rep-collapsed verdict (**lower = better**): each
  judge's verdict is the 3-class label nearest its `p̂(j,t)`; `d_c` is the fraction of judge-pairs
  giving *different* labels, averaged over trajectories.
- **fleiss_k** — Fleiss' κ over the **3 label categories**, chance-corrected agreement
  (**higher = better**; 1 perfect, 0 chance, <0 worse than chance).
- **corr_out** — Pearson correlation (across trajectories) of the item's mean grade with the
  deterministic **outcome_correct** (agent's verdict matched the silver label). +1 predictive,
  0 orthogonal. Shown only with `--job`. Small n per scenario ⇒ directional.

The per-item judge×judge covariance is written to the `--cov-out` JSON sidecar.
"""

# Review thresholds — triage heuristics (not hard rules), same defaults as the process study;
# rep_noise/κ live on the same 0–1 scales so the bars carry over.
_T_REP_NOISE = 0.10
_T_FLEISS = 0.40
_T_CORR_PROXY = 0.90
_T_LOW_DISCRIM = 0.02
_T_REP_NOISE_TIE = 0.003


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--cov-out", default="")
    ap.add_argument("--scenarios-dir", default=str(_DEFAULT_SCENARIOS_DIR))
    ap.add_argument(
        "--job",
        action="append",
        default=[],
        metavar="FAMILY=JOBDIR",
        help="repeatable; load per-trajectory outcome_correct for the corr_out column",
    )
    args = ap.parse_args()

    rubric_defs = _load_rubric_defs(Path(args.scenarios_dir))
    job_dirs = []
    for spec in args.job:
        fam, _, path = spec.partition("=")
        if path:
            job_dirs.append((fam, Path(path)))
    outcomes = _load_outcomes(job_dirs)

    rows = [r for r in load(args.inp) if not r.get("error") and r.get("grades")]
    judges = sorted({r["judge_model"] for r in rows})
    scenarios = sorted({r["scenario_id"] for r in rows})

    # index: (scenario, item, judge, task) -> [score per rep, dropping None/n-a]; and item order per scenario
    cell: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    item_order: dict[str, list[str]] = {}
    for r in rows:
        traj = (r["agent_family"], r["task_id"])
        for iid, score in r["grades"].items():
            if score is None:
                continue  # not-applicable this trajectory — excluded, like the scorer
            cell[r["scenario_id"]][iid][r["judge_model"]][traj].append(float(score))
            item_order.setdefault(r["scenario_id"], [])
            if iid not in item_order[r["scenario_id"]]:
                item_order[r["scenario_id"]].append(iid)

    out_lines: list[str] = []
    cov_dump: dict = {}

    def emit(s=""):
        out_lines.append(s)

    emit(
        f"# Policy judge-panel analysis\n\njudges: {judges}\nscenarios: {scenarios}\nrows: {len(rows)}\n"
    )
    emit(_METHODS)

    disagreement_rank: list[tuple] = []  # (d_c, scenario, item, fleiss)
    item_stats: list[dict] = []

    emit("\n# Per-scenario item tables\n")
    emit("*One row per rubric item for that scenario; columns are the metrics defined above.*")
    for scenario in scenarios:
        emit(f"\n## {scenario}\n")
        cdefs = rubric_defs.get(scenario, {})
        if cdefs:
            emit("**Items — what each measures:**\n")
            for iid in item_order.get(scenario, []):
                info = cdefs.get(iid, {})
                emit(
                    f"- **{iid}** ({info.get('kind','?')}, {info.get('weight','?')}) — {info.get('title', '(definition not found)')}"
                )
            emit("")
        oc_col = " | corr_out" if outcomes else ""
        emit(
            "item | meanScore | rep_noise | between_traj | between_judge | disagree_dc | fleiss_k"
            + oc_col
        )
        emit("---|---|---|---|---|---|---" + ("|---" if outcomes else ""))
        for iid in item_order.get(scenario, []):
            perjudge = cell[scenario][iid]  # judge -> task -> [rep scores]
            tasks = sorted({t for j in perjudge for t in perjudge[j]})
            pbar = {j: {t: _mean(perjudge[j][t]) for t in perjudge[j]} for j in perjudge}
            rep_noise = _mean([_pvar(perjudge[j][t]) for j in perjudge for t in perjudge[j]])
            between_traj = _mean([_pvar(list(pbar[j].values())) for j in pbar if pbar[j]])
            between_judge = _mean(
                [
                    _pvar([pbar[j][t] for j in pbar if t in pbar[j]])
                    for t in tasks
                    if sum(1 for j in pbar if t in pbar[j]) >= 2
                ]
            )
            mean_s = _mean([pb for j in pbar for pb in pbar[j].values()])
            # rep-collapsed verdict per (judge, task) = class nearest pbar; disagreement + Fleiss over 3 cats
            verdict = {j: {t: _nearest_class(pbar[j][t]) for t in pbar[j]} for j in pbar}
            dis_terms = []
            for t in tasks:
                js = [j for j in judges if t in verdict.get(j, {})]
                for a, b in itertools.combinations(js, 2):
                    dis_terms.append(1 if verdict[a][t] != verdict[b][t] else 0)
            d_c = _mean(dis_terms)
            ratings = [[verdict[j][t] for j in judges if t in verdict.get(j, {})] for t in tasks]
            fk = _fleiss_kappa(ratings, len(_CLASSES))
            corr = None
            if outcomes:
                xs, ys = [], []
                for t in tasks:
                    if t in outcomes:
                        vals = [pbar[j][t] for j in pbar if t in pbar[j]]
                        if vals:
                            xs.append(_mean(vals))
                            ys.append(outcomes[t])
                corr = _pearson(xs, ys)
            oc_cell = "" if not outcomes else (" | NA" if corr is None else f" | {corr:+.2f}")
            emit(
                f"{iid} | {mean_s:.2f} | {rep_noise:.3f} | {between_traj:.3f} | {between_judge:.3f} | "
                f"{d_c:.2f} | {'NA' if fk is None else f'{fk:.2f}'}{oc_cell}"
            )
            disagreement_rank.append((d_c, scenario, iid, fk))
            item_stats.append(
                {
                    "scenario": scenario,
                    "iid": iid,
                    "meanScore": mean_s,
                    "rep_noise": rep_noise,
                    "between_traj": between_traj,
                    "d_c": d_c,
                    "fk": fk,
                    "corr": corr,
                }
            )
            common = [t for t in tasks if all(t in pbar[j] for j in judges)]
            if len(common) >= 2:
                cov_dump[f"{scenario}/{iid}"] = {
                    "n_common_traj": len(common),
                    "cov": {
                        j1: {
                            j2: round(
                                _pcov([pbar[j1][t] for t in common], [pbar[j2][t] for t in common]),
                                4,
                            )
                            for j2 in judges
                        }
                        for j1 in judges
                    },
                }

    # ── Aggregate-reward reproducibility: propagate to the weighted-mean policy_outcome_pct ──
    emit("\n## Aggregate-reward reproducibility\n")
    emit(
        "*For one (judge, trajectory) the policy score is the weighted MEAN of the applicable item "
        "scores, `s = Σ_c a_c·g_c` with `a_c = 100·w_c / Σ w` over the items scored on "
        "that trajectory (n/a items excluded) — the 0–100 `policy_outcome_pct`. Its rep-to-rep SD "
        "is the aggregate's reproducibility noise.*\n\n"
        "*- **SD_actual** — measured `SD_r(s)`, averaged over (judge, trajectory).*\n"
        "*- **SD_indep** — prediction if items were independent across reps, "
        "`sqrt(Σ_c a_c²·Var_r(g_c))`. actual/indep ≈ 1 ⇒ independence; "
        "> 1 ⇒ items co-flip and amplify swings.*\n"
    )
    # group rows by (scenario, judge, traj) -> list of per-rep grade dicts
    grp: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        grp[r["scenario_id"]][(r["judge_model"], (r["agent_family"], r["task_id"]))].append(
            r["grades"]
        )
    weights_by_scenario: dict[str, dict] = {}
    for scenario in scenarios:
        cdefs = rubric_defs.get(scenario, {})
        weights_by_scenario[scenario] = {
            iid: _wabs(info.get("weight")) for iid, info in cdefs.items()
        } or None

    def _agg_for(reps: list[dict], weights: dict) -> tuple[float, float] | None:
        """(SD_actual, SD_indep) over reps for one (judge, traj); None if <2 reps or nothing scored."""
        if len(reps) < 2:
            return None
        # items applicable on ALL reps (score not None everywhere) — the scorer's per-traj set
        iids = [i for i in weights if all(gd.get(i) is not None for gd in reps)]
        if not iids:
            return None
        wsum = sum(weights[i] for i in iids) or 1.0
        a = {i: 100.0 * weights[i] / wsum for i in iids}
        s = [sum(a[i] * float(gd[i]) for i in iids) for gd in reps]
        vals = {i: [float(gd[i]) for gd in reps] for i in iids}
        sd_act = _pvar(s) ** 0.5
        sd_ind = sum(a[i] ** 2 * _pvar(vals[i]) for i in iids) ** 0.5
        return sd_act, sd_ind

    ov_act: list[float] = []
    ov_ind: list[float] = []
    by_scenario: dict[str, tuple[list, list]] = {}
    by_judge: dict[str, tuple[list, list]] = {j: ([], []) for j in judges}
    for scenario in scenarios:
        weights = weights_by_scenario.get(scenario)
        if not weights:
            by_scenario[scenario] = None
            continue
        sd_act, sd_ind = [], []
        for (judge, _traj), reps in grp[scenario].items():
            r = _agg_for(reps, weights)
            if r is None:
                continue
            sd_act.append(r[0])
            sd_ind.append(r[1])
            if judge in by_judge:
                by_judge[judge][0].append(r[0])
                by_judge[judge][1].append(r[1])
        by_scenario[scenario] = (sd_act, sd_ind) if sd_act else None
        ov_act += sd_act
        ov_ind += sd_ind

    def _delta_row(name, act, ind):
        if not act:
            return f"{name} | (insufficient reps) |  |  | "
        ma, mi = _mean(act), _mean(ind)
        ratio = f"{ma / mi:.2f}" if mi > 1e-9 else "NA"
        return f"{name} | {ma:.1f} | {mi:.1f} | {ratio} | {len(act)}"

    emit("**By scenario:**\n")
    emit("scenario | SD_actual (pp) | SD_indep (pp) | actual/indep | n(judge×traj)")
    emit("---|---|---|---|---")
    for scenario in scenarios:
        v = by_scenario.get(scenario)
        emit(_delta_row(scenario, *v) if v else f"{scenario} | (no rubric weights loaded) |  |  | ")
    if ov_act:
        emit(_delta_row("**overall**", ov_act, ov_ind))

    emit("\n**By judge** (its `SD_indep` is that judge's aggregate-reward delta):\n")
    emit("judge | SD_actual (pp) | SD_indep (pp) | actual/indep | n(traj)")
    emit("---|---|---|---|---")
    for j in judges:
        emit(_delta_row(j, *by_judge[j]))

    # Overall inter-judge agreement
    kappas = [c["fk"] for c in item_stats if c["fk"] is not None]
    overall_kappa = _mean(kappas) if kappas else None
    if overall_kappa is not None:
        emit(
            f"\n## Overall inter-judge agreement\n\nMean Fleiss κ = **{overall_kappa:.2f}** "
            f"across {len(kappas)} items (3-class, chance-corrected). Higher ⇒ the panel measures "
            "the policy rubric consistently."
        )

    # Most-contested items
    emit("\n## Most-contested rubric items (rank by mean pairwise disagreement)\n")
    emit(
        "*Items across all scenarios ranked by `disagree_dc` (highest first) — the wording most in need "
        "of tightening. `fleiss_k` is the chance-corrected companion.*\n"
    )
    emit("rank | scenario | item | measures | disagree_dc | fleiss_k")
    emit("---|---|---|---|---|---")
    for i, (dc, scenario, iid, fk) in enumerate(sorted(disagreement_rank, reverse=True)[:15], 1):
        title = rubric_defs.get(scenario, {}).get(iid, {}).get("title", "")
        emit(
            f"{i} | {scenario} | {iid} | {title} | {dc:.2f} | {'NA' if fk is None else f'{fk:.2f}'}"
        )

    # Panel-majority alignment: per (scenario, item, traj), the panel's majority verdict class; each
    # judge's maj_agree = fraction of items where its verdict matches the panel majority.
    agree_num = {j: 0 for j in judges}
    agree_den = {j: 0 for j in judges}
    for scenario in scenarios:
        for iid in item_order.get(scenario, []):
            perjudge = cell[scenario][iid]
            for t in {tt for j in perjudge for tt in perjudge[j]}:
                votes = {
                    j: _nearest_class(_mean(perjudge[j][t])) for j in perjudge if t in perjudge[j]
                }
                if len(votes) < 2:
                    continue
                cnt = Counter(votes.values())
                top, n_top = cnt.most_common(1)[0]
                if sum(1 for v in cnt.values() if v == n_top) > 1:
                    continue  # no unique majority
                for j, v in votes.items():
                    agree_den[j] += 1
                    agree_num[j] += int(v == top)
    maj_agree = {j: (agree_num[j] / agree_den[j] if agree_den[j] else None) for j in judges}

    # Per-judge self-consistency, leniency, consensus alignment
    emit("\n## Judge self-consistency, leniency & consensus alignment (pooled over all items)\n")
    emit(
        "*Per judge: `mean_rep_noise` = self-consistency across reps (lower = steadier); "
        "`mean_score` = leniency (higher = grants more 'followed'); `maj_agree` = fraction of "
        "(item, trajectory) items where the judge's verdict matches the panel majority; "
        "`n_gradings` = applicable item-grades contributing.*\n"
    )
    emit("judge | mean_rep_noise | mean_score | maj_agree | n_gradings")
    emit("---|---|---|---|---")
    judge_summary: list[tuple] = []
    for j in judges:
        noises, scores = [], []
        for scenario in scenarios:
            for iid in item_order.get(scenario, []):
                for t, reps in cell[scenario][iid].get(j, {}).items():
                    noises.append(_pvar(reps))
                    scores.append(_mean(reps))
        ma = maj_agree[j]
        emit(
            f"{j} | {_mean(noises):.3f} | {_mean(scores):.2f} | {'NA' if ma is None else f'{ma:.2f}'} | {len(scores)}"
        )
        judge_summary.append((j, _mean(noises), _mean(scores), len(scores), ma))

    # Recommended judge: among the reliable (max n_gradings), those within _T_REP_NOISE_TIE of the
    # steadiest, pick the highest consensus alignment — combined signal, not rep-noise alone.
    if judge_summary:
        nmax = max(x[3] for x in judge_summary)
        reliable = [x for x in judge_summary if x[3] == nmax] or judge_summary
        best_noise = min(x[1] for x in reliable)
        tied = [x for x in reliable if x[1] <= best_noise + _T_REP_NOISE_TIE]
        rec = max(tied, key=lambda x: (x[4] or 0, -x[1]))
        emit(
            f"\n**Recommended judge (combined):** **{rec[0]}** — steadiest reliable judge by "
            f"consensus alignment: rep-noise {rec[1]:.3f}, maj_agree "
            f"{'NA' if rec[4] is None else f'{rec[4]:.0%}'}, mean_score {rec[2]:.2f}. "
            "(rep-variance + consensus + no parse failures, not rep-variance alone.)"
        )

    # Rubrics to review
    emit("\n## Rubrics to review (threshold-flagged)\n")
    emit(
        "*Triage heuristics, not hard rules. Flagged when: `rep_noise` > "
        f"{_T_REP_NOISE} (noisy judge); `fleiss_k` < {_T_FLEISS} (low agreement); `between_traj` "
        f"< {_T_LOW_DISCRIM} while 0.1 < `meanScore` < 0.9 (weak discrimination); or |`corr_out`| "
        f"≥ {_T_CORR_PROXY} (near-perfect outcome correlation — redundant proxy or the load-bearing "
        "step; inspect either way).*\n"
    )
    review: list[tuple[dict, list[str]]] = []
    for c in item_stats:
        flags = []
        if c["rep_noise"] > _T_REP_NOISE:
            flags.append(f"noisy (rep_noise {c['rep_noise']:.2f})")
        if c["fk"] is not None and c["fk"] < _T_FLEISS:
            flags.append(f"low-agreement (κ {c['fk']:+.2f})")
        if 0.1 < c["meanScore"] < 0.9 and c["between_traj"] < _T_LOW_DISCRIM:
            flags.append(f"weak-discrimination (between_traj {c['between_traj']:.3f})")
        if c["corr"] is not None and abs(c["corr"]) >= _T_CORR_PROXY:
            flags.append(f"outcome-proxy (corr_out {c['corr']:+.2f})")
        if flags:
            review.append((c, flags))
    n_review = len(review)
    if not review:
        emit("*None — every item passed all thresholds.*")
    else:
        emit("scenario | item | measures | flags")
        emit("---|---|---|---")
        for c, flags in sorted(review, key=lambda x: -len(x[1])):
            title = rubric_defs.get(c["scenario"], {}).get(c["iid"], {}).get("title", "")
            emit(f"{c['scenario']} | {c['iid']} | {title} | {'; '.join(flags)}")

    # Family bias (DiD) — needs >=2 agent families
    agent_fams = sorted({r["agent_family"] for r in rows})
    if len(agent_fams) < 2:
        emit(
            f"\n## Family bias\n\nSkipped — only one agent family present ({agent_fams}); the "
            "judge_family × agent_family contrast needs both."
        )
    else:

        def cell_mean(jf, af):
            vals = [
                float(s)
                for r in rows
                if _judge_family(r["judge_model"]) == jf and r["agent_family"] == af
                for s in r["grades"].values()
                if s is not None
            ]
            return _mean(vals)

        jfs = sorted({_judge_family(r["judge_model"]) for r in rows})
        emit("\n## Family bias (difference-in-differences)\n")
        emit(
            "*Mean grade split by judge family × agent family; DiD subtracts the agent-quality and "
            "judge-leniency main effects, leaving own-family favoritism (>0).*\n"
        )
        emit("judge_fam \\ agent_fam | " + " | ".join(agent_fams))
        emit("---|" + "|".join("---" for _ in agent_fams))
        for jf in jfs:
            emit(f"{jf} | " + " | ".join(f"{cell_mean(jf, af):.2f}" for af in agent_fams))
        if {"gpt", "claude"} <= set(jfs) and {"gpt", "claude"} <= set(agent_fams):
            did = (cell_mean("claude", "claude") - cell_mean("claude", "gpt")) - (
                cell_mean("gpt", "claude") - cell_mean("gpt", "gpt")
            )
            emit(
                f"\n**DiD (own-family favoritism)** = **{did:+.3f}** (>0 → each family grades its own "
                "agent higher; ~0 → no family effect)."
            )

    # Takeaways
    emit("\n## Takeaways\n")
    emit(
        "*Auto-generated from the numbers above. Caveats: small n per scenario (directional); this "
        "measures judge reliability/agreement, NOT correctness (no gold policy labels).*\n"
    )
    if judge_summary:
        best = min(judge_summary, key=lambda x: x[1])
        worst = max(judge_summary, key=lambda x: x[1])
        emit(
            f"- **Judge reliability.** Steadiest: **{best[0]}** (rep-noise {best[1]:.3f}); least: "
            f"{worst[0]} ({worst[1]:.3f}). Leniency (mean_score) spans "
            f"{min(x[2] for x in judge_summary):.2f}–{max(x[2] for x in judge_summary):.2f}."
        )
    if overall_kappa is not None:
        emit(f"- **Panel agreement.** Mean 3-class Fleiss κ = {overall_kappa:.2f}.")
    active = [c for c in item_stats if 0 < c["meanScore"] < 1]
    nd = [c for c in active if c["rep_noise"] > c["between_traj"]]
    if active:
        emit(
            f"- **Noise vs signal.** {len(nd)}/{len(active)} items that ever vary are noise-dominated "
            "(rep-noise > between-trajectory) — rep-averaging is what makes them usable."
        )
    top = [x for x in sorted(disagreement_rank, reverse=True)[:3] if x[0] > 0]
    if top:
        emit(
            "- **Tighten these.** Judges disagree most on: "
            + "; ".join(f"{scenario} {iid} (d_c {dc:.2f})" for dc, scenario, iid, _fk in top)
            + "."
        )
    if n_review:
        emit(
            f"- **Rubrics to review.** {n_review} item(s) tripped a review threshold — see that section."
        )

    report = "\n".join(out_lines)
    if args.out:
        Path(args.out).write_text(report)
        print(f"wrote report -> {args.out}")
    else:
        print(report)
    if args.cov_out and cov_dump:
        Path(args.cov_out).write_text(json.dumps(cov_dump, indent=2))
        print(f"wrote covariance matrices -> {args.cov_out}")


if __name__ == "__main__":
    main()
