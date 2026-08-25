"""Phase 2 of the judge-panel study: from the per-(trajectory, judge, rep) grades emitted by
judge_panel.py, compute the reliability / agreement / bias metrics and write a report.

Unit of analysis is (scenario, criterion) — criteria are scenario-specific, so we never pool *different*
criteria; we pool *trajectories* within a scenario (and pool across criteria only for the balanced
family-bias contrast). Each grade is boolean (met/not-met); weights are deterministic and only
used to optionally prioritize contested dimensions.

Metrics (per scenario+criterion unless noted):
  A. mean P(met) per judge + variance decomposition: rep-noise (judge stochasticity),
     between-trajectory (discrimination signal), between-judge (model disagreement).
  B. judge self-consistency: mean rep-noise per (criterion, judge).
  C. cross-judge covariance matrix (over trajectories, rep-averaged) — written to a JSON sidecar.
  D. disagreement ranking: mean pairwise disagreement rate d_c and Fleiss' kappa (chance-
     corrected). d_c/kappa are preferred over "min covariance entry" (which isn't chance-
     corrected and degenerates for near-unanimous criteria).
  E. family bias: difference-in-differences of P(met) over (judge_family x agent_family),
     which cancels overall agent-quality and judge-leniency main effects.

Plus, to drive the judge/rubric selection loop: per-judge consensus alignment (maj_agree) and
aggregate-reward delta, an overall Fleiss kappa, a "Selecting a judge & rubric set" framing, and
a threshold-flagged "rubrics to review" list. The chosen judge should combine low rep-variance,
high maj_agree, and no parse failures — not rep-variance alone.

  python benchmark/eval/reliability/judge_analysis.py --in jobs/judge_panel.jsonl \
      --job claude=<jobdir> [--job gpt=<jobdir>] \
      --out jobs/judge_panel_report.md --cov-out jobs/judge_panel_cov.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import tomllib
from collections import defaultdict
from pathlib import Path


def _wint(w) -> int:
    """Signed integer weight from a rubric weight string like '+2' / '-1'."""
    m = re.search(r"[+-]?\d+", str(w) if w is not None else "")
    return int(m.group()) if m else 0


_DEFAULT_SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "_scenarios"


def _load_rubric_defs(scenarios_dir: Path) -> dict[str, dict[str, dict]]:
    """{scenario_id: {criterion_id: {"title", "weight"}}} from _scenarios/*/rubrics.toml.

    Lets the report say what each criterion measures; the panel JSONL only carries ids.
    Degrades to {} if the scenarios dir isn't present (report then falls back to bare ids)."""
    defs: dict[str, dict[str, dict]] = {}
    if not scenarios_dir.is_dir():
        return defs
    for d in sorted(scenarios_dir.glob("scenario-*")):
        scenario_toml, rub_toml = d / "scenario.toml", d / "rubrics.toml"
        if not (scenario_toml.is_file() and rub_toml.is_file()):
            continue
        try:
            cid = tomllib.loads(scenario_toml.read_text())["id"]
            rubrics = tomllib.loads(rub_toml.read_text()).get("rubric", [])
        except (ValueError, KeyError):
            continue
        defs[cid] = {
            r["id"]: {"title": r.get("title", ""), "weight": r.get("weight", "")}
            for r in rubrics
            if "id" in r
        }
    return defs


_METHODS = r"""
## How to read this report

**What we did.** Each *trajectory* (one agent rollout on one task) is graded by every *judge
model*, $R$ times ("reps"), on each *criterion* of that task's process rubric. A grade is
**boolean**: $1$ = "met" (the agent did what the criterion describes), $0$ = "not met" — rubric
weights are deterministic and not used here. Analysis is **per (scenario, criterion)**: we pool
over the trajectories within a scenario, never across different criteria (criteria differ by scenario).

**Notation.** For a fixed criterion, let $g_{j,t,r}\in\{0,1\}$ be judge $j$'s grade of
trajectory $t$ on rep $r$, and $\hat p_{j,t}=\frac{1}{R}\sum_r g_{j,t,r}$ its rep-averaged
grade. $\operatorname{Var}(x)=\operatorname{mean}\!\big((x-\bar x)^2\big)$ is the population
variance; $j$ ranges over judges, $t$ over trajectories.

**Metrics (per criterion):**
- **meanP** — overall met-rate: $\ \operatorname{meanP}=\operatorname*{mean}_{j,t,r} g_{j,t,r}$.
  NL: how often the criterion is judged met, across all judges/trajectories/reps.
- **rep_noise** — judge stochasticity (**lower = better**):
  $\ \operatorname*{mean}_{j,t}\ \hat p_{j,t}\,(1-\hat p_{j,t})$.
  NL: how much one judge flips across its *own* reps on the same trajectory ($0$ = identical
  every rep). This is the noise the reps exist to measure.
- **between_traj** — discrimination signal (**higher = better**):
  $\ \operatorname*{mean}_{j}\operatorname{Var}_{t}\big(\hat p_{j,t}\big)$.
  NL: how much the criterion separates *different* trajectories; $\approx 0$ = uninformative.
- **between_judge** — cross-judge spread:
  $\ \operatorname*{mean}_{t}\operatorname{Var}_{j}\big(\hat p_{j,t}\big)$.
  NL: how much judges disagree with each other on the *same* trajectory.
- **disagree_dc** — mean pairwise disagreement (**lower = better**). With the per-judge majority
  vote $m_{j,t}=\mathbf 1\!\left[\hat p_{j,t}\ge 0.5\right]$:
  $\ d_c=\operatorname*{mean}_{t,\ j<k}\ \mathbf 1\!\left[m_{j,t}\neq m_{k,t}\right]$.
  NL: the fraction of the time two judges reach opposite verdicts on a trajectory.
- **fleiss_k** — Fleiss' $\kappa$, chance-corrected agreement (**higher = better**):
  $\ \kappa=\dfrac{\bar P-P_e}{1-P_e}$, with per-trajectory agreement
  $P_i=\dfrac{\sum_{c}n_{ic}^2-n}{n(n-1)}$ ($n$ judges, $n_{ic}$ of them voting category
  $c\in\{0,1\}$ on trajectory $i$), $\bar P=\operatorname*{mean}_i P_i$, and chance term
  $P_e=\sum_c p_c^2$ ($p_c$ = overall proportion voting $c$). NL: agreement *beyond chance* —
  $1$ perfect, $0$ chance, $<0$ worse than chance. Shown as $1.00$ when every judge agrees on
  every trajectory. Raters = judges (majority-voted over reps); subjects = trajectories.

- **corr_out** — correlation with the primary **outcome reward** (only shown when `--job` is
  given). Let $o_t\in\{0,1\}$ be the deterministic outcome for trajectory $t$ (the agent's
  4-class verdict matched the silver label) and $\bar p_{t}=\operatorname*{mean}_{j}
  \hat p_{j,t}$ the criterion's mean grade for $t$. corr_out is the Pearson correlation
  $\operatorname{corr}_t\!\big(\bar p_{t},\,o_t\big)$ across trajectories. NL: does performing
  this process step predict getting the final answer right? $+1$ = strongly predictive,
  $0$ = orthogonal, $<0$ = anti-predictive. NA if the criterion or the outcome is constant.
  **Small $n$ per scenario** (a handful of trajectories) — read as directional, not precise.

The per-criterion judge$\times$judge **covariance**
$\operatorname{Cov}_t\!\big(\hat p_{j,t},\hat p_{k,t}\big)$ is written to the `--cov-out` JSON
sidecar, not inlined here.
"""

# Review thresholds — triage heuristics (not hard rules) for the "rubrics to review" section.
_T_REP_NOISE = 0.10  # judge stochasticity too high
# Contested-criterion trigger. We flag on `disagree_dc` (mean pairwise judge disagreement), NOT on
# Fleiss `fleiss_k` < 0.40: kappa suffers the base-rate paradox — a skewed criterion (met-rate ≈ 0
# or 1, e.g. a MUST-NOT almost never met) collapses to κ ≈ 0 / negative even when judges agree on
# nearly every trajectory, so a κ<0.4 flag fired on ~30% false positives (judges actually agreeing)
# while missing genuine disagreement that kept κ above 0.4. disagree_dc is not chance-corrected, so
# it reads real "opposite verdicts" rate directly. fleiss_k is still shown as a companion column.
_T_DISAGREE = (
    0.20  # mean pairwise judge disagreement above this ⇒ contested (needs tighter wording)
)
_T_CORR_PROXY = 0.90  # |corr_out| this high ⇒ criterion largely restates the outcome
_T_LOW_DISCRIM = 0.02  # between_traj this low (while the criterion varies) ⇒ weak discrimination
_T_LENIENCY_SPREAD = 0.10  # met-rate spread across judges above this ⇒ Fleiss kappa optimistic
_T_REP_NOISE_TIE = 0.003  # rep-noise gaps this small are within measurement noise ⇒ treat as tied

_SELECTION = """
## Selecting a judge & rubric set

This report is the measurement layer for a selection loop; the calls below are ultimately
**human judgment** on the numbers.

1. **Pick the judge.** Favor one that is *self-consistent* (low `mean_rep_noise`), *aligned
   with the panel consensus* (high `maj_agree`), and *reliable* (full `n_gradings` — no parse
   failures) — not rep-variance alone, since the steadiest model can still be the flakiest to
   parse. When two judges' `rep_noise` differ by less than measurement noise (a few thousandths
   over thousands of gradings), treat them as tied and let `maj_agree` decide — otherwise a
   leniency/consensus outlier can win on a hair of rep-noise. Its aggregate-reward **delta** is
   its `SD_indep` in the per-judge table.
2. **Filter / adapt rubrics.** Flag a criterion for review when its judge stochasticity
   (`rep_noise`) is high, judges reach opposite verdicts too often (`disagree_dc` high — this,
   not `fleiss_k`, which the base-rate paradox collapses on skewed criteria), it barely
   discriminates trajectories (`between_traj` ≈ 0), or its outcome correlation (`corr_out`) is
   extreme. A
   near-±1 `corr_out` cuts both ways and is a judgment call: it can mean the criterion is a
   *redundant proxy* for the deterministic outcome reward (drop it) **or** that it captures the
   genuinely *load-bearing* step (keep it). The "rubrics to review" section lists the flagged
   ones; it recommends inspection, not automatic removal.
3. **Check aggregate stability.** Confirm the chosen judge's aggregate **delta** (`SD_indep`)
   is within your tolerance; tighten rubrics and re-run until it is.
"""


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
    """Pearson r; None if <2 points or either series is constant (r undefined)."""
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    vx, vy = _pvar(xs), _pvar(ys)
    if vx <= 1e-12 or vy <= 1e-12:
        return None
    return _pcov(xs, ys) / (vx**0.5 * vy**0.5)


def _load_outcomes(job_dirs: list[tuple[str, Path]]) -> dict[tuple[str, str], int]:
    """{(agent_family, task_id): outcome_correct} from each trial's verifier/reward.json.

    outcome_correct is the deterministic primary reward (agent verdict == silver label),
    judge-independent, so it's read once per trajectory rather than per grading."""
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


def _judge_family(model: str) -> str:
    m = model.lower()
    if "gpt" in m or "openai" in m:
        return "gpt"
    if "claude" in m or "sonnet" in m or "haiku" in m or "opus" in m:
        return "claude"
    return "other"


def _fleiss_kappa(ratings_per_subject: list[list[int]]) -> float | None:
    """ratings_per_subject: for each subject (trajectory), a list of one 0/1 rating per rater
    (judge). Requires the same rater count per subject; subjects with fewer are dropped."""
    n_raters = max((len(r) for r in ratings_per_subject), default=0)
    subj = [r for r in ratings_per_subject if len(r) == n_raters]
    if n_raters < 2 or len(subj) < 2:
        return None
    cats = [0, 1]
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
        return 1.0  # perfect + degenerate (everyone always agrees on one category)
    return (p_bar - p_e) / (1 - p_e)


def load(path: str) -> list[dict]:
    return [json.loads(ln) for ln in Path(path).read_text().splitlines() if ln.strip()]


def _emit_takeaways(
    emit,
    crit_stats,
    judge_summary,
    agg,
    disagreement_rank,
    did_value,
    agent_fams,
    overall_kappa=None,
    n_review=0,
):
    """Synthesis section, derived entirely from the computed numbers (valid for any input)."""
    emit("\n## Takeaways\n")
    emit(
        "*Auto-generated from the numbers above. Caveats apply: small $n$ per scenario (directional), "
        "and this measures judge reliability/agreement, not correctness (no gold process labels).*\n"
    )
    if judge_summary:
        best = min(judge_summary, key=lambda x: x[1])
        worst = max(judge_summary, key=lambda x: x[1])
        lens = [x[2] for x in judge_summary]
        nmax = max(x[3] for x in judge_summary)
        fails = [x for x in judge_summary if x[3] < nmax]
        fail_txt = (
            "; ".join(f"{x[0]} missing {nmax - x[3]} gradings (parse failures)" for x in fails)
            if fails
            else "no grading failures"
        )
        emit(
            f"- **Judge reliability.** Most self-consistent: **{best[0]}** (rep-noise "
            f"{best[1]:.3f}); least: {worst[0]} ({worst[1]:.3f}). Leniency $P(\\text{{met}})$ "
            f"spans {min(lens):.2f}–{max(lens):.2f}. {fail_txt}."
        )
        aligned = [x for x in judge_summary if len(x) > 4 and x[4] is not None]
        if aligned:
            top = max(aligned, key=lambda x: x[4])
            emit(
                f"- **Consensus alignment.** Judge most often matching the panel majority: "
                f"**{top[0]}** ({top[4]:.0%}); least: {min(aligned, key=lambda x: x[4])[0]} "
                f"({min(x[4] for x in aligned):.0%})."
            )
        # Recommended judge: among the reliable ones (no parse failures), take the group whose
        # rep-noise is within _T_REP_NOISE_TIE of the steadiest — gaps that small are within
        # measurement noise over thousands of gradings — then pick the highest consensus
        # alignment (maj_agree). This stops a marginally-steadier leniency/consensus outlier from
        # winning on a hair of rep-noise; it combines the signals rather than rep-noise alone.
        reliable = [x for x in judge_summary if x[3] == nmax]
        pool = reliable or judge_summary
        best_noise = min(x[1] for x in pool)
        tied = [x for x in pool if x[1] <= best_noise + _T_REP_NOISE_TIE]
        rec = max(tied, key=lambda x: (x[4] or 0, -x[1]))
        note = "" if reliable else " (all judges had some parse failures)"
        tie_note = (
            f", tie-broken by consensus among the {len(tied)} judges within "
            f"{_T_REP_NOISE_TIE:.3f} rep-noise of the steadiest"
            if len(tied) > 1
            else ""
        )
        emit(
            f"- **Recommended judge (combined).** **{rec[0]}** — best consensus alignment among "
            f"the steadiest reliable judges{note}: rep-noise {rec[1]:.3f}, maj_agree "
            f"{'NA' if rec[4] is None else f'{rec[4]:.0%}'}{tie_note}. (rep-variance + consensus + "
            f"no parse failures, not rep-variance alone.)"
        )
    if overall_kappa is not None:
        emit(
            f"- **Panel agreement.** Mean Fleiss $\\kappa$ = {overall_kappa:.2f} across criteria "
            "(chance-corrected inter-judge agreement)."
        )
    if agg:
        rtxt = f"{agg['ratio']:.2f}" if agg.get("ratio") is not None else "NA"
        xtxt = f"{agg['xcorr']:+.2f}" if agg.get("xcorr") is not None else "NA"
        emit(
            f"- **Aggregate stability.** A single judge's `process_pct` swings ~{agg['sd_actual']:.1f} "
            f"pp (1σ) rep-to-rep; averaging over reps/judges shrinks it ~$\\sqrt{{N}}$. "
            f"Independence-predicted {agg['sd_indep']:.1f} pp (actual/indep {rtxt}), cross-criterion "
            f"corr {xtxt} ⇒ dimensions approximately independent across reps."
        )
    active = [c for c in crit_stats if 0 < c["meanP"] < 1]
    nd = [c for c in active if c["rep_noise"] > c["between_traj"]]
    if active:
        emit(
            f"- **Noise vs signal.** {len(nd)}/{len(active)} criteria that ever vary are "
            f"noise-dominated (rep-noise > between-trajectory): their grade tracks judge "
            f"stochasticity more than agent differences, so rep-averaging is what makes them usable."
        )
    top = sorted(disagreement_rank, reverse=True)[:3]
    if top and top[0][0] > 0:
        parts = [
            f"{scenario} {cid} (d_c {dc:.2f}, κ {'NA' if fk is None else f'{fk:+.2f}'})"
            for dc, scenario, cid, fk in top
        ]
        emit("- **Tighten these.** Judges disagree most on: " + "; ".join(parts) + ".")
    withc = [c for c in crit_stats if c["corr"] is not None]
    if withc:
        pred = sorted(withc, key=lambda c: c["corr"], reverse=True)[:3]
        orth = [c for c in withc if abs(c["corr"]) < 0.1]
        ptxt = "; ".join(f"{c['scenario']} {c['cid']} ({c['corr']:+.2f})" for c in pred)
        emit(
            f"- **Load-bearing steps.** Most outcome-predictive process criteria: {ptxt}. "
            f"{len(orth)}/{len(withc)} are ~orthogonal to the outcome (|corr| < 0.1) — they gauge "
            f"process quality independent of final-answer correctness."
        )
    if n_review:
        emit(
            f"- **Rubrics to review.** {n_review} criteria tripped a review threshold "
            "(noisy / contested / weak-discrimination / outcome-proxy) — see that section."
        )
    if len(agent_fams) >= 2 and did_value is not None:
        verdict = "negligible" if abs(did_value) < 0.05 else "notable"
        emit(f"- **Family bias.** DiD = {did_value:+.3f} ⇒ {verdict} own-family favoritism.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--cov-out", default="")
    ap.add_argument(
        "--scenarios-dir",
        default=str(_DEFAULT_SCENARIOS_DIR),
        help="_scenarios/ dir for criterion titles (default: sibling of scripts/)",
    )
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

    # index: (scenario, crit, judge, task) -> [met per rep]; and criterion order per scenario
    cell: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    crit_order: dict[str, list[str]] = {}
    for r in rows:
        traj = (r["agent_family"], r["task_id"])  # a trajectory = one agent's rollout of a task
        for cid, met in r["grades"].items():
            cell[r["scenario_id"]][cid][r["judge_model"]][traj].append(met)
            crit_order.setdefault(r["scenario_id"], [])
            if cid not in crit_order[r["scenario_id"]]:
                crit_order[r["scenario_id"]].append(cid)

    out_lines: list[str] = []
    cov_dump: dict = {}

    def emit(s=""):
        out_lines.append(s)

    emit(f"# Judge-panel analysis\n\njudges: {judges}\nscenarios: {scenarios}\nrows: {len(rows)}\n")
    emit(_METHODS)
    emit(_SELECTION)

    disagreement_rank: list[tuple] = []  # (d_c, scenario, crit, fleiss)
    crit_stats: list[dict] = []  # per-criterion metrics, for the Takeaways synthesis
    agg: dict = {}  # aggregate-reproducibility overall numbers, filled below
    judge_summary: list[tuple] = []  # (judge, mean_rep_noise, mean_P, n_gradings)
    did_value: float | None = None  # family-bias DiD, if computed

    emit("\n# Per-scenario criterion tables\n")
    emit(
        "*One row per rubric criterion for that scenario; each column is a metric defined in "
        "“How to read this report” above.*"
    )
    for scenario in scenarios:
        emit(f"\n## {scenario}\n")
        cdefs = rubric_defs.get(scenario, {})
        if cdefs:
            emit("**Criteria — what each measures:**\n")
            for cid in crit_order[scenario]:
                info = cdefs.get(cid, {})
                w = info.get("weight", "?")
                emit(f"- **{cid}** ({w}) — {info.get('title', '(definition not found)')}")
            emit("")
        oc_col = " | corr_out" if outcomes else ""
        emit(
            "criterion | meanP | rep_noise | between_traj | between_judge | disagree_dc | "
            "fleiss_k" + oc_col
        )
        emit("---|---|---|---|---|---|---" + ("|---" if outcomes else ""))
        for cid in crit_order[scenario]:
            perjudge = cell[scenario][cid]  # judge -> task -> [reps]
            tasks = sorted({t for j in perjudge for t in perjudge[j]})
            # rep-averaged grade pbar[judge][task]
            pbar = {j: {t: _mean(perjudge[j][t]) for t in perjudge[j]} for j in perjudge}
            # A: rep-noise = mean over (judge,task) of pbar(1-pbar)
            rep_noise = _mean([pb * (1 - pb) for j in pbar for pb in pbar[j].values()])
            # between-trajectory (discrimination): per judge var over tasks of pbar, mean over judges
            between_traj = _mean([_pvar(list(pbar[j].values())) for j in pbar if pbar[j]])
            # between-judge (disagreement magnitude): per task var over judges of pbar, mean over tasks
            between_judge = _mean(
                [
                    _pvar([pbar[j][t] for j in pbar if t in pbar[j]])
                    for t in tasks
                    if sum(1 for j in pbar if t in pbar[j]) >= 2
                ]
            )
            mean_p = _mean([pb for j in pbar for pb in pbar[j].values()])
            # D: majority vote per (judge, task); pairwise disagreement + Fleiss
            maj = {j: {t: (1 if pbar[j][t] >= 0.5 else 0) for t in pbar[j]} for j in pbar}
            dis_terms = []
            for t in tasks:
                js = [j for j in judges if t in maj.get(j, {})]
                for a, b in itertools.combinations(js, 2):
                    dis_terms.append(1 if maj[a][t] != maj[b][t] else 0)
            d_c = _mean(dis_terms)
            ratings = [[maj[j][t] for j in judges if t in maj.get(j, {})] for t in tasks]
            fk = _fleiss_kappa(ratings)
            # corr with the outcome reward: per-trajectory criterion grade (mean over judges)
            # vs the deterministic outcome_correct.
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
                f"{cid} | {mean_p:.2f} | {rep_noise:.3f} | {between_traj:.3f} | "
                f"{between_judge:.3f} | {d_c:.2f} | {'NA' if fk is None else f'{fk:.2f}'}{oc_cell}"
            )
            disagreement_rank.append((d_c, scenario, cid, fk))
            crit_stats.append(
                {
                    "scenario": scenario,
                    "cid": cid,
                    "meanP": mean_p,
                    "rep_noise": rep_noise,
                    "between_traj": between_traj,
                    "d_c": d_c,
                    "fk": fk,
                    "corr": corr,
                }
            )
            # C: covariance matrix over tasks (rep-averaged), common tasks only
            common = [t for t in tasks if all(t in pbar[j] for j in judges)]
            if len(common) >= 2:
                mat = {
                    j1: {
                        j2: round(
                            _pcov([pbar[j1][t] for t in common], [pbar[j2][t] for t in common]), 4
                        )
                        for j2 in judges
                    }
                    for j1 in judges
                }
                cov_dump[f"{scenario}/{cid}"] = {"n_common_traj": len(common), "cov": mat}

    # Aggregate-reward reproducibility: propagate per-criterion rep-noise to process_pct.
    emit("\n## Aggregate-reward reproducibility\n")
    emit(
        "*For one (judge, trajectory) the linear process score is $s=\\sum_c a_c\\,g_c$ with "
        "$a_c=100\\,w_c/\\sum_{w>0}w$ (so $s$ is on the 0–100 process_pct scale). Its rep-to-rep "
        "standard deviation is the aggregate reward's reproducibility noise.*\n\n"
        "*- **SD_actual** — measured $\\operatorname{SD}_r(s)$, averaged over (judge, trajectory).*\n"
        "*- **SD_indep** — the prediction if criteria were independent across reps, "
        "$\\sqrt{\\sum_c a_c^2\\operatorname{Var}(g_c)}$ (i.e. summing the individual rubric-score "
        "variances). **actual/indep** $\\approx 1$ ⇒ independence holds; $>1$ ⇒ criteria co-flip "
        "(positive covariance) and amplify swings.*\n"
        "*- **xcrit_corr** — mean Pearson correlation across reps between pairs of criteria that "
        "vary within a (judge, trajectory); $\\approx 0$ confirms dimensions are uncorrelated "
        "across reps. Small $n$ — directional.*\n"
    )
    grp: dict = defaultdict(lambda: defaultdict(list))  # scenario -> (judge, traj) -> [grade dicts]
    for r in rows:
        grp[r["scenario_id"]][(r["judge_model"], (r["agent_family"], r["task_id"]))].append(
            r["grades"]
        )
    ov_act: list[float] = []
    ov_ind: list[float] = []
    ov_xc: list[float] = []
    by_scenario: dict[str, tuple[list, list, list]] = {}
    by_judge: dict[str, tuple[list, list, list]] = {j: ([], [], []) for j in judges}
    for scenario in scenarios:
        weights = {
            cid: _wint(info.get("weight")) for cid, info in rubric_defs.get(scenario, {}).items()
        }
        possible = sum(w for w in weights.values() if w > 0)
        if possible <= 0:
            by_scenario[scenario] = None
            continue
        a = {cid: 100.0 * w / possible for cid, w in weights.items()}
        sd_act: list[float] = []
        sd_ind: list[float] = []
        xc: list[float] = []
        for (judge, _traj), reps in grp[scenario].items():
            if len(reps) < 2:
                continue
            cids = [c for c in weights if any(c in gd for gd in reps)]
            vals = {c: [gd.get(c, 0) for gd in reps] for c in cids}
            s = [sum(a[c] * vals[c][i] for c in cids) for i in range(len(reps))]
            act = _pvar(s) ** 0.5
            ind = sum(a[c] ** 2 * _pvar(vals[c]) for c in cids) ** 0.5
            flip = [c for c in cids if _pvar(vals[c]) > 1e-12]
            pair_xc = []
            for i in range(len(flip)):
                for k in range(i + 1, len(flip)):
                    rc = _pearson(vals[flip[i]], vals[flip[k]])
                    if rc is not None:
                        pair_xc.append(rc)
            sd_act.append(act)
            sd_ind.append(ind)
            xc += pair_xc
            if judge in by_judge:
                by_judge[judge][0].append(act)
                by_judge[judge][1].append(ind)
                by_judge[judge][2].extend(pair_xc)
        by_scenario[scenario] = (sd_act, sd_ind, xc) if sd_act else None
        ov_act += sd_act
        ov_ind += sd_ind
        ov_xc += xc

    def _delta_row(name, act, ind, xc):
        if not act:
            return f"{name} | (insufficient reps) |  |  |  | "
        ma, mi = _mean(act), _mean(ind)
        ratio = f"{ma / mi:.2f}" if mi > 1e-9 else "NA"
        mx = f"{_mean(xc):+.2f}" if xc else "NA"
        return f"{name} | {ma:.1f} | {mi:.1f} | {ratio} | {mx} | {len(act)}"

    emit("**By scenario:**\n")
    emit("scenario | SD_actual (pp) | SD_indep (pp) | actual/indep | xcrit_corr | n(judge×traj)")
    emit("---|---|---|---|---|---")
    for scenario in scenarios:
        v = by_scenario.get(scenario)
        emit(
            _delta_row(scenario, *v)
            if v
            else f"{scenario} | (no rubric weights loaded) |  |  |  | "
        )
    if ov_act:
        emit(_delta_row("**overall**", ov_act, ov_ind, ov_xc))
        agg = {
            "sd_actual": _mean(ov_act),
            "sd_indep": _mean(ov_ind),
            "ratio": (_mean(ov_act) / _mean(ov_ind) if _mean(ov_ind) > 1e-9 else None),
            "xcorr": (_mean(ov_xc) if ov_xc else None),
        }

    emit("\n**By judge** (the chosen judge's `SD_indep` is its aggregate-reward delta):\n")
    emit("judge | SD_actual (pp) | SD_indep (pp) | actual/indep | xcrit_corr | n(traj)")
    emit("---|---|---|---|---|---")
    for j in judges:
        emit(_delta_row(j, *by_judge[j]))

    # Overall inter-judge agreement (single number)
    kappas = [c["fk"] for c in crit_stats if c["fk"] is not None]
    overall_kappa = _mean(kappas) if kappas else None
    if overall_kappa is not None:
        emit(
            f"\n## Overall inter-judge agreement\n\nMean Fleiss $\\kappa$ = **{overall_kappa:.2f}** "
            f"across {len(kappas)} criteria (chance-corrected; 1 = perfect, 0 = chance, "
            "<0 = worse than chance). Higher ⇒ the panel is measuring the rubric consistently."
        )

    # D: global disagreement ranking
    emit("\n## Most-contested rubric dimensions (rank by mean pairwise disagreement)\n")
    emit(
        "*Criteria across all scenarios ranked by `disagree_dc` (highest first) — the dimensions "
        "where judges most often reach opposite verdicts, i.e. the wording most in need of "
        "tightening. `fleiss_k` is the chance-corrected companion (lower/negative = worse).*\n"
    )
    emit("rank | scenario | criterion | measures | disagree_dc | fleiss_k")
    emit("---|---|---|---|---|---")
    for i, (dc, scenario, cid, fk) in enumerate(sorted(disagreement_rank, reverse=True)[:15], 1):
        title = rubric_defs.get(scenario, {}).get(cid, {}).get("title", "")
        emit(
            f"{i} | {scenario} | {cid} | {title} | {dc:.2f} | {'NA' if fk is None else f'{fk:.2f}'}"
        )

    # Panel-majority agreement: per (scenario, criterion, trajectory), the panel majority vote over
    # judges' rep-collapsed grades; each judge's maj_agree = fraction of items it matches it on.
    agree_num = {j: 0 for j in judges}
    agree_den = {j: 0 for j in judges}
    for scenario in scenarios:
        for cid in crit_order[scenario]:
            perjudge = cell[scenario][cid]
            for t in {tt for j in perjudge for tt in perjudge[j]}:
                votes = {
                    j: (1 if _mean(perjudge[j][t]) >= 0.5 else 0)
                    for j in perjudge
                    if t in perjudge[j]
                }
                if len(votes) < 2:
                    continue
                ones, n = sum(votes.values()), len(votes)
                if ones * 2 == n:
                    continue  # tie — no majority
                pmaj = 1 if ones * 2 > n else 0
                for j, v in votes.items():
                    agree_den[j] += 1
                    agree_num[j] += int(v == pmaj)
    maj_agree = {j: (agree_num[j] / agree_den[j] if agree_den[j] else None) for j in judges}

    # B: per-judge self-consistency + leniency
    emit("\n## Judge self-consistency, leniency & consensus alignment (pooled over all criteria)\n")
    emit(
        "*Per judge model, pooled over every (criterion, trajectory, rep): `mean_rep_noise` = "
        "self-consistency across reps (lower = steadier); `mean_P(met)` = leniency (higher = "
        "grants more criteria); `maj_agree` = fraction of (criterion, trajectory) items where the "
        "judge's majority-vote grade matches the **panel majority** (higher = most "
        "consensus-aligned); `n_gradings` = criterion-grades contributing (fewer ⇒ some gradings "
        "failed to parse).*\n"
    )
    emit("judge | mean_rep_noise | mean_P(met) | maj_agree | n_gradings")
    emit("---|---|---|---|---")
    for j in judges:
        jr = [r for r in rows if r["judge_model"] == j]
        allmet = [m for r in jr for m in r["grades"].values()]
        # rep noise per (crit,task) for this judge
        noises = []
        for scenario in scenarios:
            for cid in crit_order[scenario]:
                for t, reps in cell[scenario][cid].get(j, {}).items():
                    pb = _mean(reps)
                    noises.append(pb * (1 - pb))
        ma = maj_agree[j]
        ma_txt = "NA" if ma is None else f"{ma:.2f}"
        emit(f"{j} | {_mean(noises):.3f} | {_mean(allmet):.2f} | {ma_txt} | {len(allmet)}")
        judge_summary.append((j, _mean(noises), _mean(allmet), len(allmet), ma))

    # Interchangeability sanity check on the Fleiss assumption. Fleiss' kappa uses one pooled
    # marginal for its chance term, so it assumes every judge shares the same met-rate; a judge
    # that is systematically more/less lenient breaks that and makes kappa optimistic. Simple
    # diagnostic: the spread of mean_P(met) across judges, and the judge furthest from the mean.
    mets = {j: mp for (j, _rn, mp, _n, _ma) in judge_summary}
    if len(mets) >= 2:
        pbar = _mean(list(mets.values()))
        lenient = max(mets, key=lambda j: mets[j])
        strict = min(mets, key=lambda j: mets[j])
        spread = mets[lenient] - mets[strict]
        outlier = max(mets, key=lambda j: abs(mets[j] - pbar))
        verdict = (
            "Within tolerance — judges are ~interchangeable, so the kappa above is trustworthy"
            if spread <= _T_LENIENCY_SPREAD
            else f"Above the {_T_LENIENCY_SPREAD:.0%} tolerance — kappa is optimistic; treat the "
            "outlier as a poor default judge"
        )
        emit("\n## Rater interchangeability (Fleiss $\\kappa$ sanity check)\n")
        emit(
            "*Fleiss $\\kappa$ assumes raters are **interchangeable** — a 'met' means the same "
            "thing from any judge, i.e. they share one marginal met-rate — and credits systematic "
            "leniency differences as if they were chance agreement. Quick check: the spread of "
            "`mean_P(met)` across judges (from the table above). A large spread ⇒ $\\kappa$ is "
            "optimistic and the outlier judge is a poor default.*\n"
        )
        emit(
            f"Met-rate spread across judges = **{spread*100:.1f} pp** "
            f"(most lenient **{lenient}** at {mets[lenient]:.2f}, most strict **{strict}** at "
            f"{mets[strict]:.2f}; panel mean {pbar:.2f}). Furthest from the mean: **{outlier}** "
            f"({mets[outlier]-pbar:+.2f}). {verdict}."
        )

    # Rubrics to review: threshold-flag criteria that warrant inspection.
    emit("\n## Rubrics to review (threshold-flagged)\n")
    emit(
        "*Triage heuristics, not hard rules — final calls are human judgment. A criterion is "
        f"flagged when: `rep_noise` > {_T_REP_NOISE} (noisy judge); `disagree_dc` ≥ {_T_DISAGREE} "
        "(contested — judges reach opposite verdicts this often; paradox-free, unlike Fleiss κ which "
        f"a skewed met-rate collapses); `between_traj` < {_T_LOW_DISCRIM} while "
        "0.1 < `meanP` < 0.9 (weak discrimination — same grade regardless of trajectory); or "
        f"|`corr_out`| ≥ {_T_CORR_PROXY} (near-perfect outcome correlation — may be a redundant "
        "proxy for the deterministic reward, or the load-bearing step; inspect either way).*\n"
    )
    review: list[tuple[dict, list[str]]] = []
    for c in crit_stats:
        flags = []
        if c["rep_noise"] > _T_REP_NOISE:
            flags.append(f"noisy (rep_noise {c['rep_noise']:.2f})")
        if c["d_c"] >= _T_DISAGREE:
            fk_txt = "NA" if c["fk"] is None else f"{c['fk']:+.2f}"
            flags.append(f"contested (disagree_dc {c['d_c']:.2f}, κ {fk_txt})")
        if 0.1 < c["meanP"] < 0.9 and c["between_traj"] < _T_LOW_DISCRIM:
            flags.append(f"weak-discrimination (between_traj {c['between_traj']:.3f})")
        if c["corr"] is not None and abs(c["corr"]) >= _T_CORR_PROXY:
            flags.append(f"outcome-proxy (corr_out {c['corr']:+.2f})")
        if flags:
            review.append((c, flags))
    if not review:
        emit("*None — every criterion passed all thresholds.*")
    else:
        emit("scenario | criterion | measures | flags")
        emit("---|---|---|---")
        for c, flags in sorted(review, key=lambda x: -len(x[1])):
            title = rubric_defs.get(c["scenario"], {}).get(c["cid"], {}).get("title", "")
            emit(f"{c['scenario']} | {c['cid']} | {title} | {'; '.join(flags)}")

    # E: family bias DiD — needs >=2 agent families; skip (don't crash) for a single-family run.
    agent_fams = sorted({r["agent_family"] for r in rows})
    jfs = sorted({_judge_family(r["judge_model"]) for r in rows})
    if len(agent_fams) < 2:
        emit(
            f"\n## Family bias\n\nSkipped — only one agent family present ({agent_fams}); "
            "the judge_family x agent_family contrast needs both."
        )
    else:
        emit("\n## Family bias (difference-in-differences)\n")
        emit(
            "*Does a judge favor agents from its own model family? The table below is mean "
            "$P(\\text{met})$ split by judge family $\\times$ agent family. Writing "
            "$\\bar g_{xy}$ for the mean $P(\\text{met})$ of a judge in family $x$ on an agent in "
            "family $y$ ($c$ = claude, $g$ = gpt), the **difference-in-differences** is*\n\n"
            "$$\\mathrm{DiD}=\\big(\\bar g_{cc}-\\bar g_{cg}\\big)-\\big(\\bar g_{gc}-\\bar g_{gg}\\big).$$\n\n"
            "*It subtracts out the two main effects — overall agent quality ($\\bar g_{\\cdot c}$ vs "
            "$\\bar g_{\\cdot g}$) and overall judge leniency — leaving only own-family favoritism: "
            "$>0 \\Rightarrow$ each family scores its own agent higher; $\\approx 0 \\Rightarrow$ no "
            "family effect. Judge family is inferred from the model name.*"
        )

        def cell_mean(jf, af):
            vals = [
                m
                for r in rows
                if _judge_family(r["judge_model"]) == jf and r["agent_family"] == af
                for m in r["grades"].values()
            ]
            return _mean(vals), len(vals)

        emit(f"agent families: {agent_fams} | judge families: {jfs}")
        emit("\nmean P(met) by (judge_family, agent_family):\n")
        emit("judge_fam \\ agent_fam | " + " | ".join(agent_fams))
        emit("---|" + "|".join("---" for _ in agent_fams))
        for jf in jfs:
            cells = [cell_mean(jf, af)[0] for af in agent_fams]
            emit(f"{jf} | " + " | ".join(f"{c:.2f}" for c in cells))
        if {"gpt", "claude"} <= set(jfs) and {"gpt", "claude"} <= set(agent_fams):
            cj_ca = cell_mean("claude", "claude")[0]
            cj_ga = cell_mean("claude", "gpt")[0]
            gj_ca = cell_mean("gpt", "claude")[0]
            gj_ga = cell_mean("gpt", "gpt")[0]
            did_value = (cj_ca - cj_ga) - (gj_ca - gj_ga)
            emit(
                f"\n**DiD (own-family favoritism)** = (claudeJ: claudeA−gptA) − (gptJ: claudeA−gptA)"
                f" = ({cj_ca:.2f}−{cj_ga:.2f}) − ({gj_ca:.2f}−{gj_ga:.2f}) = **{did_value:+.3f}**"
            )
            emit(
                "(> 0 → each family grades its own agent's trajectories higher; ~0 → no family "
                "effect)"
            )

    _emit_takeaways(
        emit,
        crit_stats,
        judge_summary,
        agg,
        disagreement_rank,
        did_value,
        agent_fams,
        overall_kappa=overall_kappa,
        n_review=len(review),
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
