"""Paired case-level significance tests for the CliniCARE-Bench leaderboard.

Emits the statistics a ranking claim rests on, which `score_clinicare.py` does not compute: whether
two systems are actually separable, the tier structure that follows, whether the defect-free
correction reorders the leaderboard, and how reliable the case set is as a measuring instrument.

WHY PAIRED. Every system answers the same frozen cases, so per-system accuracies are correlated
through shared case difficulty. At n = 750 one system's binomial standard error is about +-1.6
points, so marginal intervals overlap heavily across the whole observed spread and invite the
conclusion that nothing is distinguishable. That reasoning discards the pairing: the cases every
system gets right and the cases none of them get inflate the marginal error and cancel in a paired
comparison. Two systems can therefore have visibly overlapping error bars in a figure and still
separate here, which is not a contradiction -- marginal error bars describe one system, these tests
compare two.

Run it over job dirs, one per system, exactly like `score_clinicare.py`:

    python benchmark/eval/report/paired_tests.py jobs/<job>

Each job dir must hold one graded trial per task id. Only cases present in EVERY job are used, so
each contrast is complete over the same cases; the number dropped is reported. Trial loading is
`score_clinicare.load_trial`, so gold recovery, the MUST-NOT trap flag, and the display labels all
behave identically to the scorer -- this module owns no loading logic of its own.

DEFINITIONS

    accuracy        exact four-class agreement with the reference verdict, over ALL cases;
                    a missing or unparseable verdict counts as incorrect
    defect-free     correct AND no MUST-NOT criterion sprung, over REPORT-PRESENT cases only,
                    because a case with no report has no observable process to grade
    defect gap      raw minus defect-free over that same report-present denominator. Never
                    subtract defect-free from all-case accuracy: that conflates non-delivery with
                    sprung traps, and on one sweep turned a 7.8-point gap into an apparent 3.5.
                    For the same reason a pair's defect-free test uses only the cases where BOTH
                    systems produced a report, so one system's infrastructure failure cannot be
                    scored as the other's process defect
    McNemar         exact two-sided test on the discordant pairs. Conditional on the number of
                    disagreements the split is Binomial(n_d, 0.5) under the null, computed by
                    complete enumeration rather than a chi-squared approximation, because some
                    discordant counts are small
    BH / Holm       Benjamini-Hochberg controls the expected PROPORTION of false calls among the
                    pairs called significant; Holm controls the probability of ANY false call.
                    Both are reported: 120 comparisons at an uncorrected 0.05 would yield about six
                    false positives by chance, and quoting one correction alone invites the question
                    of whether the other was tried
    tiers           a system opens a new tier when it separates from the CURRENT TIER'S LEADER.
                    Tiers are not transitive and are not cliques: a boundary means the leader
                    separated, not that every pair spanning it did
    alpha           Cronbach's alpha over the cases x systems outcome matrix -- the share of
                    variance in system totals attributable to real differences between systems
                    rather than to which cases were sampled. Reliability, NOT validity: it says the
                    instrument is consistent, not that the labels are right

Pure standard library, so this adds no dependency.
"""

from __future__ import annotations

import argparse
import glob
import itertools
import json
import math
import os
import random
import statistics as st

from clinicare_core.paths import bootstrap

bootstrap(__file__, "report")
from score_clinicare import job_task_dir, load_trial, row_label  # noqa: E402

LACK = "INDETERMINATE_LACK_OF_DATA"
AMB = "INDETERMINATE_MEDICAL_AMBIGUITY"
DEFERRAL = (LACK, AMB)
DEFINITIVE = ("YES", "NO")
ALPHA = 0.05


# ----------------------------------------------------------------------------- statistics


def binomial_se(pct: float, n: int) -> float:
    """+-1 standard error on a percentage, matching the paper's figures."""
    if not n:
        return 0.0
    p = pct / 100.0
    return 100.0 * math.sqrt(p * (1 - p) / n)


def mcnemar_exact(a_wins: int, b_wins: int) -> float:
    """Exact two-sided McNemar P value on the discordant pairs."""
    nd = a_wins + b_wins
    if nd == 0:
        return 1.0
    lo = min(a_wins, b_wins)
    tail = sum(math.comb(nd, i) for i in range(lo + 1)) / 2**nd
    return min(1.0, 2 * tail)


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted P values, input order preserved."""
    m = len(pvals)
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(sorted(range(m), key=lambda i: pvals[i])):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    """BH adjusted P values (q values), input order preserved."""
    m = len(pvals)
    adj = [0.0] * m
    running = 1.0
    for rank, i in enumerate(sorted(range(m), key=lambda i: pvals[i], reverse=True)):
        running = min(running, m * pvals[i] / (m - rank))
        adj[i] = running
    return adj


def pearson(a: list[float], b: list[float]) -> float | None:
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den if den else None


def _ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a: list[float], b: list[float]) -> float | None:
    return pearson(_ranks(a), _ranks(b))


def kendall_tau(a: list[float], b: list[float]) -> float | None:
    con = dis = 0
    for i, j in itertools.combinations(range(len(a)), 2):
        s = (a[i] - a[j]) * (b[i] - b[j])
        con += s > 0
        dis += s < 0
    return (con - dis) / (con + dis) if con + dis else None


def cronbach_alpha(matrix: list[list[int]]) -> float | None:
    """matrix: rows = systems, cols = cases, binary outcomes."""
    if len(matrix) < 2 or len(matrix[0]) < 2:
        return None
    n_items = len(matrix[0])
    item_var = sum(st.pvariance([row[j] for row in matrix]) for j in range(n_items))
    total_var = st.pvariance([sum(row) for row in matrix])
    if not total_var:
        return None
    return (n_items / (n_items - 1)) * (1 - item_var / total_var)


def split_half(matrix: list[list[int]], draws: int = 200, seed: int = 0) -> float | None:
    """Split-half reliability with the Spearman-Brown correction, averaged over random splits.

    Reported next to alpha because alpha assumes roughly equal item contributions and this does
    not; two estimators agreeing is a stronger statement than either alone.
    """
    rng = random.Random(seed)
    items = list(range(len(matrix[0])))
    vals = []
    for _ in range(draws):
        rng.shuffle(items)
        h1, h2 = items[: len(items) // 2], items[len(items) // 2 :]
        r = pearson(
            [sum(row[j] for j in h1) for row in matrix],
            [sum(row[j] for j in h2) for row in matrix],
        )
        # Spearman-Brown is 2r/(1+r), which assumes the halves positively correlate as
        # measures of the same thing. r = -1 divides by zero and any r <= 0 yields a
        # coefficient outside [0, 1); both are reachable on tiny case sets, where a single
        # split can correlate perfectly or perversely. Such draws are dropped rather than
        # averaged in, and if every draw is dropped the estimate is reported as undefined.
        if r is not None and 0 < r < 1:
            vals.append(2 * r / (1 + r))
    return st.mean(vals) if vals else None


# ----------------------------------------------------------------------------- loading


def disambiguate_labels(systems: list[dict]) -> None:
    """Force every system label to be distinct, in place.

    Everything downstream keys on the label (`by_label`, the McNemar lookup, the rank maps), so a
    duplicate silently collapses two runs into one and compares a run against itself, reporting
    zero discordance and a spurious tie. `row_label` derives from harness x model, so any two runs
    of the same system collide -- comparing one arm across two sweeps is a normal use of this
    tool, not an exotic one.

    A job's basename is not enough to separate them, because sweeps are usually laid out as
    `<sweep>/<arm>/` and the arm component repeats. Use the shortest trailing path fragment that
    actually distinguishes the colliding jobs, so the label names the directory a reader would
    need to tell them apart.
    """
    # Identical paths are the same run listed twice, which is self-comparison rather than
    # something to label; drop the repeats instead of numbering them.
    seen_paths = set()
    deduped = []
    for s in systems:
        key = os.path.realpath(s["job"])
        if key in seen_paths:
            print(f"  ignoring duplicate job dir {s['job']}")
            continue
        seen_paths.add(key)
        deduped.append(s)
    systems[:] = deduped

    groups: dict[str, list[dict]] = {}
    for s in systems:
        groups.setdefault(s["label"], []).append(s)
    for base, group in groups.items():
        if len(group) < 2:
            continue
        parts = [[p for p in s["job"].rstrip(os.sep).split(os.sep) if p] for s in group]
        for depth in range(1, max(len(p) for p in parts) + 1):
            frags = [os.sep.join(p[-depth:]) for p in parts]
            if len(set(frags)) == len(frags):
                for s, frag in zip(group, frags):
                    s["label"] = f"{base} [{frag}]"
                break

    # Distinct paths can still produce one label if two different bases disambiguate onto the
    # same string, so make uniqueness a guarantee rather than a likelihood.
    final: dict[str, int] = {}
    for s in systems:
        n = final.get(s["label"], 0) + 1
        final[s["label"]] = n
        if n > 1:
            s["label"] = f"{s['label']} #{n}"


def load_system(job_dir: str) -> dict:
    """One job dir -> {label, trials: {task_id: trial}}."""
    task_dir = job_task_dir(job_dir)
    trials = {}
    for d in sorted(glob.glob(os.path.join(job_dir, "*/"))):
        t = load_trial(d, task_dir)
        if t is None:
            continue
        trials[os.path.basename(d.rstrip("/")).rsplit("__", 1)[0]] = t
    return {"label": row_label(job_dir), "job": job_dir, "trials": trials}


def summarize(sys_: dict, tasks: list[str]) -> dict:
    ts = [sys_["trials"][k] for k in tasks]
    n = len(ts)
    rp = [t for t in ts if t.get("report_present") != 0]
    rp_correct = sum(t["score"] for t in rp)
    rp_clean = sum(1 for t in rp if t["score"] and not t.get("trapped"))
    defer = [t for t in ts if t.get("gt") in DEFERRAL]
    defin = [t for t in ts if t.get("gt") in DEFINITIVE]
    return {
        "label": sys_["label"],
        "n": n,
        "n_rp": len(rp),
        "acc": 100 * sum(t["score"] for t in ts) / n if n else 0.0,
        "raw_rp": 100 * rp_correct / len(rp) if rp else None,
        "defect_free": 100 * rp_clean / len(rp) if rp else None,
        "gap": 100 * (rp_correct - rp_clean) / len(rp) if rp else None,
        "overcommit": (
            100 * sum(1 for t in defer if t.get("pred") in DEFINITIVE) / len(defer)
            if defer
            else None
        ),
        "overabstain": (
            100 * sum(1 for t in defin if t.get("pred") in DEFERRAL) / len(defin) if defin else None
        ),
        "n_defer": len(defer),
        "n_defin": len(defin),
    }


# ----------------------------------------------------------------------------- tests


def outcome_accuracy(t: dict) -> int:
    return t["score"]


def outcome_defect_free(t: dict) -> int | None:
    """None drops the case from a pair's denominator -- see the module docstring."""
    if t.get("report_present") == 0:
        return None
    return int(bool(t["score"]) and not t.get("trapped"))


def paired_tests(systems: list[dict], tasks: list[str], outcome) -> list[dict]:
    out = []
    for a, b in itertools.combinations(range(len(systems)), 2):
        aw = bw = 0
        n_paired = 0
        for k in tasks:
            oa, ob = outcome(systems[a]["trials"][k]), outcome(systems[b]["trials"][k])
            if oa is None or ob is None:
                continue
            n_paired += 1
            aw += oa and not ob
            bw += ob and not oa
        out.append(
            {
                "a": systems[a]["label"],
                "b": systems[b]["label"],
                "a_wins": aw,
                "b_wins": bw,
                "n_paired": n_paired,
                "p": mcnemar_exact(aw, bw),
            }
        )
    ps = [r["p"] for r in out]
    for r, q, h in zip(out, benjamini_hochberg(ps), holm(ps)):
        r["p_bh"], r["p_holm"] = q, h
    return out


def tiers(rows: list[dict], results: list[dict], key: str, field: str) -> list[list[dict]]:
    sig = {}
    for r in results:
        sig[(r["a"], r["b"])] = sig[(r["b"], r["a"])] = r[field] < ALPHA
    order = sorted((r for r in rows if r[key] is not None), key=lambda r: -r[key])
    if not order:
        return []
    grouped, current, leader = [], [order[0]], order[0]
    for r in order[1:]:
        if sig.get((r["label"], leader["label"]), False):
            grouped.append(current)
            current, leader = [r], r
        else:
            current.append(r)
    grouped.append(current)
    return grouped


# ----------------------------------------------------------------------------- output


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("jobs", nargs="+", help="job dirs or globs, one per system")
    ap.add_argument("--json", help="write per-system rows and all pairwise tests here")
    args = ap.parse_args()

    job_dirs = [d for pat in args.jobs for d in sorted(glob.glob(pat)) if os.path.isdir(d)]
    if len(job_dirs) < 2:
        print("need at least two job dirs to compare")
        return 2

    systems = [load_system(d) for d in job_dirs]
    dropped = [s["job"] for s in systems if not s["trials"]]
    systems = [s for s in systems if s["trials"]]
    for d in dropped:
        print(f"  skipped {d}: no gradeable trials")
    # Dedup first: the count guard has to see the number of *distinct* runs, or passing the same
    # job dir twice slips past it as two systems and then collapses to one.
    disambiguate_labels(systems)

    if len(systems) < 2:
        print(
            f"need at least two distinct systems with gradeable trials; found {len(systems)}. "
            "Each job dir must contain trial subdirectories with verifier/reward.json."
        )
        return 2

    common = set.intersection(*(set(s["trials"]) for s in systems))
    union = set().union(*(set(s["trials"]) for s in systems))
    tasks = sorted(common)
    print(f"{len(systems)} systems; {len(tasks)} cases common to all ({len(union)} in union)")
    if len(union) != len(common):
        print(f"  dropped {len(union) - len(common)} case(s) absent from at least one job")
    if not tasks:
        print(
            "no case id is present in every job dir, so no paired comparison is possible. "
            "Check that the job dirs ran the same task build."
        )
        return 2

    rows = sorted((summarize(s, tasks) for s in systems), key=lambda r: -r["acc"])
    by_label = {s["label"]: s for s in systems}
    ordered = [by_label[r["label"]] for r in rows]

    print("\n== per-system ==")
    print(f"{'system':34s} {'acc':>12s} {'d-free':>12s} {'gap':>6s} {'o-com':>7s} {'o-abs':>7s}")
    for r in rows:
        acc = f"{r['acc']:.1f}±{binomial_se(r['acc'], r['n']):.1f}"
        dfr = (
            f"{r['defect_free']:.1f}±{binomial_se(r['defect_free'], r['n_rp']):.1f}"
            if r["defect_free"] is not None
            else "-"
        )
        print(
            f"{r['label']:34s} {acc:>12s} {dfr:>12s} "
            f"{r['gap'] if r['gap'] is not None else float('nan'):6.1f} "
            f"{r['overcommit'] if r['overcommit'] is not None else float('nan'):7.1f} "
            f"{r['overabstain'] if r['overabstain'] is not None else float('nan'):7.1f}"
        )

    acc_res = paired_tests(ordered, tasks, outcome_accuracy)
    df_res = paired_tests(ordered, tasks, outcome_defect_free)
    n_pairs = len(acc_res)

    print(f"\n== paired exact McNemar, {n_pairs} pairs ==")
    for name, res in (("verdict accuracy", acc_res), ("defect-free accuracy", df_res)):
        parts = ", ".join(
            f"{sum(1 for r in res if r[f] < ALPHA)} {lab}"
            for f, lab in (
                ("p", "uncorrected"),
                ("p_bh", "BH-FDR 5%"),
                ("p_holm", "Holm"),
            )
        )
        print(f"  {name:22s} {parts} (of {n_pairs})")

    for name, res, key in (
        ("verdict accuracy", acc_res, "acc"),
        ("defect-free accuracy", df_res, "defect_free"),
    ):
        print(f"\n== tiers by {name} (BH-FDR 5%) ==")
        for i, tier in enumerate(tiers(rows, res, key, "p_bh"), 1):
            print(f"  tier {i}: " + ", ".join(f"{m['label']} ({m[key]:.1f})" for m in tier))

    # Does the defect correction reorder the leaderboard? Compare like with like: raw accuracy
    # over report-present cases, not all-case accuracy.
    scored = [r for r in rows if r["defect_free"] is not None]
    if len(scored) > 1:
        rank_raw = {r["label"]: i for i, r in enumerate(sorted(scored, key=lambda r: -r["raw_rp"]))}
        rank_df = {
            r["label"]: i for i, r in enumerate(sorted(scored, key=lambda r: -r["defect_free"]))
        }
        lookup = {}
        for r in df_res:
            lookup[(r["a"], r["b"])] = lookup[(r["b"], r["a"])] = r
        inverted = [
            (a, b)
            for a, b in itertools.combinations(scored, 2)
            if (rank_raw[a["label"]] < rank_raw[b["label"]])
            != (rank_df[a["label"]] < rank_df[b["label"]])
        ]
        print("\n== does the defect correction reorder the leaderboard? ==")
        for f, lab in (("p_bh", "BH-FDR 5%"), ("p_holm", "Holm")):
            k = sum(1 for a, b in inverted if lookup[(a["label"], b["label"])][f] < ALPHA)
            print(f"  {len(inverted)}/{n_pairs} pairs invert; {k} significant ({lab})")

        def _q(ab):
            return lookup[(ab[0]["label"], ab[1]["label"])]["p_bh"]

        for a, b in sorted(inverted, key=_q):
            r = lookup[(a["label"], b["label"])]
            if r["p_bh"] < ALPHA:
                print(
                    f"    {a['label']} vs {b['label']}: raw {a['raw_rp']:.1f}/{b['raw_rp']:.1f}"
                    f" -> defect-free {a['defect_free']:.1f}/{b['defect_free']:.1f}"
                    f"  q={r['p_bh']:.4f}"
                )
        raw_v = [r["raw_rp"] for r in scored]
        df_v = [r["defect_free"] for r in scored]
        rho, tau = spearman(raw_v, df_v), kendall_tau(raw_v, df_v)
        print(f"  Spearman rho = {rho:+.3f}" if rho is not None else "  Spearman rho = n/a")
        print(f"  Kendall tau = {tau:+.3f}" if tau is not None else "  Kendall tau = n/a")

    matrix = [[s["trials"][k]["score"] for k in tasks] for s in ordered]
    a, sb = cronbach_alpha(matrix), split_half(matrix)
    print("\n== instrument reliability ==")
    scope = f"({len(tasks)} cases x {len(ordered)} systems)"
    # Alpha is bounded above by 1 but not below, and it goes negative when the items are
    # anti-correlated -- on a handful of shared cases that is noise, not a reliability estimate.
    # The value is still printed rather than suppressed, because silently reporting "n/a" would
    # hide a real signal about the matrix, but it is marked so it cannot be quoted as a result.
    note = " (not interpretable: items anti-correlated)" if a is not None and a <= 0 else ""
    print(f"  Cronbach alpha {scope} = " + (f"{a:.3f}{note}" if a is not None else "n/a"))
    print(
        "  split-half + Spearman-Brown "
        + " " * (len(scope) - 8)
        + "= "
        + (f"{sb:.3f}" if sb is not None else "n/a")
    )

    if args.json:
        with open(args.json, "w") as fh:
            json.dump(
                {
                    "per_system": rows,
                    "pairs_accuracy": acc_res,
                    "pairs_defect_free": df_res,
                    "reliability": {
                        "cronbach_alpha": a,
                        "split_half_spearman_brown": sb,
                    },
                },
                fh,
                indent=1,
            )
        print(f"\nwrote {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
