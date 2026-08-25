"""Tests for paired_tests.py -- the statistics, and the denominator rules.

Every expected value is hand-computable from the definitions in the script's docstring, and is
asserted against that hand computation rather than against another implementation: two
implementations agreeing proves they agree, not that either is right.

    python3 benchmark/eval/tests/test_paired_tests.py
    pytest benchmark/eval/tests/test_paired_tests.py   # also collects
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

from clinicare_core.paths import bootstrap

bootstrap(__file__, "report")
import paired_tests as pt  # noqa: E402

FAILS: list[str] = []


def check(name: str, got, want, tol: float = 1e-9) -> None:
    ok = got is want or (
        isinstance(got, (int, float)) and isinstance(want, (int, float)) and abs(got - want) <= tol
    )
    if isinstance(want, (list, tuple)):
        ok = (
            got is not None
            and len(got) == len(want)
            and all(abs(g - w) <= tol for g, w in zip(got, want))
        )
    if not ok:
        FAILS.append(f"{name}: expected {want}, got {got}")


def test_mcnemar_exact():
    # 10 discordant pairs all one way: 2 * C(10,0)/2^10 = 2/1024.
    check("mcnemar(10,0)", pt.mcnemar_exact(10, 0), 2 / 1024)
    # An even split cannot be evidence of anything; the doubled tail is clamped at 1.
    check("mcnemar(5,5)", pt.mcnemar_exact(5, 5), 1.0)
    # 4 discordant, 3-1: 2 * (C(4,0)+C(4,1))/2^4 = 2 * 5/16.
    check("mcnemar(3,1)", pt.mcnemar_exact(3, 1), 0.625)
    # No disagreement at all is not significance -- it is no information.
    check("mcnemar(0,0)", pt.mcnemar_exact(0, 0), 1.0)
    # Symmetric in its arguments: the test is two-sided.
    check("mcnemar symmetry", pt.mcnemar_exact(9, 2), pt.mcnemar_exact(2, 9))


def test_corrections():
    # m=3. Holm: 3*.01=.03, 2*.02=.04, 1*.03=.03, then enforced monotone -> .03,.04,.04
    check("holm", pt.holm([0.01, 0.02, 0.03]), [0.03, 0.04, 0.04])
    # BH: 3*.03/3=.03, 3*.02/2=.03, 3*.01/1=.03, monotone from the top -> all .03
    check("bh", pt.benjamini_hochberg([0.01, 0.02, 0.03]), [0.03, 0.03, 0.03])
    # BH is never more conservative than Holm, which is the reason both are reported.
    ps = [0.001, 0.01, 0.02, 0.04, 0.3, 0.9]
    for q, h in zip(pt.benjamini_hochberg(ps), pt.holm(ps)):
        if q > h + 1e-12:
            FAILS.append(f"bh {q} exceeded holm {h}")
    # Order is preserved, so results can be zipped back onto the pair list.
    check("bh order preserved", pt.benjamini_hochberg([0.5, 0.001])[1], 0.002)


def test_reliability():
    # 3 systems x 4 cases. Item variances (population): .2222 each for the first three
    # columns, 0 for the last -> sum .6667. Totals are 3,3,0 -> variance 2.
    # alpha = (4/3)(1 - .6667/2) = .8889
    matrix = [[1, 1, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0]]
    check("cronbach", pt.cronbach_alpha(matrix), 0.888888888889, 1e-9)
    # Degenerate inputs return None rather than dividing by zero.
    check("cronbach no variance", pt.cronbach_alpha([[1, 1], [1, 1]]), None)
    check("cronbach one system", pt.cronbach_alpha([[1, 0, 1]]), None)


def test_rank_correlations():
    check("spearman", pt.spearman([1, 2, 3, 4], [2, 1, 4, 3]), 0.6)
    check("kendall", pt.kendall_tau([1, 2, 3, 4], [2, 1, 4, 3]), 1 / 3)
    check("spearman identical", pt.spearman([1, 2, 3], [10, 20, 30]), 1.0)
    check("kendall reversed", pt.kendall_tau([1, 2, 3], [3, 2, 1]), -1.0)


def test_defect_free_outcome():
    """A no-report case has no observable process, so it is dropped, not scored zero."""
    check(
        "no report -> None",
        pt.outcome_defect_free({"score": 1, "report_present": 0}),
        None,
    )
    check(
        "sprung trap -> 0",
        pt.outcome_defect_free({"score": 1, "trapped": 1, "report_present": 1}),
        0,
    )
    check(
        "clean correct -> 1",
        pt.outcome_defect_free({"score": 1, "trapped": None, "report_present": 1}),
        1,
    )
    # An ungraded process (trapped is None) counts as clean, matching score_clinicare.
    check(
        "wrong verdict -> 0",
        pt.outcome_defect_free({"score": 0, "report_present": 1}),
        0,
    )


def _trial(tmp: str, job: str, task: str, *, correct: bool, report=1, trapped=False) -> None:
    d = os.path.join(tmp, job, f"{task}__x")
    os.makedirs(os.path.join(d, "verifier"), exist_ok=True)
    json.dump(
        {"outcome_score": 1.0 if correct else 0.0, "report_present": report},
        open(os.path.join(d, "verifier/reward.json"), "w"),
    )
    json.dump(
        {"ground_truth_label": "YES", "scenario_id": "s"},
        open(os.path.join(d, "verifier/rubrics.json"), "w"),
    )
    json.dump(
        {
            "agent_label": "YES" if correct else "NO",
            "process_graded": [
                {"id": "N1", "weight": "-2", "grade": "met" if trapped else "not met"}
            ],
        },
        open(os.path.join(d, "verifier/grades_detail.json"), "w"),
    )


def test_pairing_drops_only_the_affected_pair():
    """A no-report case leaves accuracy denominators alone, and only its own pair's process one."""
    tmp = tempfile.mkdtemp()
    try:
        # 3 cases. B has no report on c3; A and C do.
        for task, a_ok, b_ok, c_ok in (
            ("c1", 1, 0, 1),
            ("c2", 1, 0, 1),
            ("c3", 1, 1, 0),
        ):
            _trial(tmp, "A", task, correct=bool(a_ok))
            _trial(tmp, "B", task, correct=bool(b_ok), report=0 if task == "c3" else 1)
            _trial(tmp, "C", task, correct=bool(c_ok))
        systems = [pt.load_system(os.path.join(tmp, j)) for j in ("A", "B", "C")]
        tasks = sorted(set.intersection(*(set(s["trials"]) for s in systems)))
        check("all cases loaded", len(tasks), 3, 0)

        acc = {(r["a"], r["b"]): r for r in pt.paired_tests(systems, tasks, pt.outcome_accuracy)}
        dfr = {(r["a"], r["b"]): r for r in pt.paired_tests(systems, tasks, pt.outcome_defect_free)}
        a_lab, b_lab, c_lab = (s["label"] for s in systems)

        # Accuracy: every pair keeps all 3 cases, because a no-report trial scores incorrect.
        for pair in ((a_lab, b_lab), (a_lab, c_lab), (b_lab, c_lab)):
            check(f"acc n_paired {pair}", acc[pair]["n_paired"], 3, 0)
        # Defect-free: only the pairs containing B lose c3.
        check("dfr n_paired A-B", dfr[(a_lab, b_lab)]["n_paired"], 2, 0)
        check("dfr n_paired B-C", dfr[(b_lab, c_lab)]["n_paired"], 2, 0)
        check("dfr n_paired A-C", dfr[(a_lab, c_lab)]["n_paired"], 3, 0)
        # A beat B on c1 and c2; c3 is excluded, so the split is 2-0 rather than 2-1.
        check("dfr A wins over B", dfr[(a_lab, b_lab)]["a_wins"], 2, 0)
        check("dfr B wins over A", dfr[(a_lab, b_lab)]["b_wins"], 0, 0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_trap_costs_defect_free_but_not_accuracy():
    tmp = tempfile.mkdtemp()
    try:
        for task in ("c1", "c2"):
            _trial(tmp, "clean", task, correct=True)
            _trial(tmp, "shortcut", task, correct=True, trapped=True)
        systems = [pt.load_system(os.path.join(tmp, j)) for j in ("clean", "shortcut")]
        tasks = sorted(set.intersection(*(set(s["trials"]) for s in systems)))
        rows = {s["label"]: pt.summarize(s, tasks) for s in systems}
        clean, short = (s["label"] for s in systems)
        check("clean acc", rows[clean]["acc"], 100.0)
        check("shortcut acc", rows[short]["acc"], 100.0)
        check("clean defect-free", rows[clean]["defect_free"], 100.0)
        check("shortcut defect-free", rows[short]["defect_free"], 0.0)
        check("shortcut gap", rows[short]["gap"], 100.0)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _job(tmp: str, job: str, tasks, *, agent: str, model: str, correct=lambda t: True) -> None:
    """A job dir whose label is derived from config.json, as `row_label` does in practice."""
    for task in tasks:
        d = os.path.join(tmp, job, f"{task}__x")
        os.makedirs(os.path.join(d, "verifier"), exist_ok=True)
        json.dump(
            {"outcome_score": 1.0 if correct(task) else 0.0, "report_present": 1},
            open(os.path.join(d, "verifier/reward.json"), "w"),
        )
        json.dump(
            {"ground_truth_label": "YES", "scenario_id": "s"},
            open(os.path.join(d, "verifier/rubrics.json"), "w"),
        )
        json.dump(
            {
                "agent_label": "YES",
                "process_graded": [{"id": "N1", "weight": "-2", "grade": "not met"}],
            },
            open(os.path.join(d, "verifier/grades_detail.json"), "w"),
        )
        json.dump(
            {"agent": {"name": agent, "model_name": model}},
            open(os.path.join(d, "config.json"), "w"),
        )


def _run(*job_dirs):
    """Invoke the CLI the way a user would; returns (exit code, stdout)."""
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(os.path.dirname(here), "report", "paired_tests.py")
    r = subprocess.run([sys.executable, script, *job_dirs], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def test_duplicate_labels_are_disambiguated():
    """Two runs of the same harness x model must stay distinct.

    `row_label` derives from harness x model, so re-running one system collides. Keying anything
    on the raw label collapses the two into one and silently compares a system against itself,
    which reports zero discordant pairs and P = 1 no matter how far apart the runs actually are.
    """
    tmp = tempfile.mkdtemp()
    try:
        _job(tmp, "runA", ("c1", "c2", "c3", "c4"), agent="codex", model="openai/gpt-5.5")
        _job(
            tmp,
            "runB",
            ("c1", "c2", "c3", "c4"),
            agent="codex",
            model="openai/gpt-5.5",
            correct=lambda t: t == "c1",
        )
        code, out = _run(os.path.join(tmp, "runA"), os.path.join(tmp, "runB"))
        check("exit code", code, 0, 0)
        if "[runA]" not in out or "[runB]" not in out:
            FAILS.append("duplicate labels were not disambiguated by job dir")
        # 100% against 25% over 4 shared cases: 3 discordant, all one way.
        if "100.0" not in out or "25.0" not in out:
            FAILS.append("collapsed systems: both accuracies should appear")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_no_common_cases_is_an_error_not_a_crash():
    tmp = tempfile.mkdtemp()
    try:
        _job(tmp, "x", ("a1", "a2"), agent="codex", model="openai/gpt-5.5")
        _job(tmp, "y", ("b1", "b2"), agent="claude-code", model="anthropic/opus-5")
        code, out = _run(os.path.join(tmp, "x"), os.path.join(tmp, "y"))
        check("exit code", code, 2, 0)
        if "Traceback" in out:
            FAILS.append("no-overlap input raised instead of reporting")
        if "no case id is present in every job dir" not in out:
            FAILS.append("no-overlap input did not explain itself")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_too_few_usable_systems_is_an_error_not_a_crash():
    tmp = tempfile.mkdtemp()
    try:
        _job(tmp, "x", ("a1", "a2"), agent="codex", model="openai/gpt-5.5")
        os.makedirs(os.path.join(tmp, "empty", "a1__x"), exist_ok=True)  # no verifier/ at all
        code, out = _run(os.path.join(tmp, "empty"), os.path.join(tmp, "x"))
        check("exit code", code, 2, 0)
        if "Traceback" in out:
            FAILS.append("unusable job dir raised instead of reporting")
        if "no gradeable trials" not in out:
            FAILS.append("unusable job dir was not named in the output")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_same_label_and_same_basename_still_disambiguates():
    """`<sweep>/<arm>/` layouts repeat the arm component, so basename alone is not unique.

    A surviving duplicate would collapse the two runs in `by_label` and compare one against
    itself, reporting zero discordance as a tie.
    """
    systems = [
        {"label": "GPT-5.5", "job": "/runs/sweepA/codex-gpt55"},
        {"label": "GPT-5.5", "job": "/runs/sweepB/codex-gpt55"},
    ]
    pt.disambiguate_labels(systems)
    labels = [s["label"] for s in systems]
    check("labels are distinct", len(set(labels)), 2)
    check("label names the sweep", "GPT-5.5 [sweepA/codex-gpt55]" in labels, True)


def test_identical_job_paths_are_dropped_not_numbered():
    """The same dir listed twice is self-comparison, so it is deduped rather than relabelled."""
    systems = [
        {"label": "GPT-5.5", "job": "/runs/codex-gpt55"},
        {"label": "GPT-5.5", "job": "/runs/codex-gpt55/"},
    ]
    pt.disambiguate_labels(systems)
    check("duplicate path dropped", len(systems), 1)
    check("label left alone", systems[0]["label"], "GPT-5.5")


def test_uniqueness_is_guaranteed_when_paths_are_indistinguishable():
    """Fallback numbering, so uniqueness never depends on the path layout cooperating."""
    # "X" over /p/a and /p/b disambiguates to "X [a]" and "X [b]", which then collides with a
    # third system whose label is already literally "X [b]". Distinct paths, same final label.
    systems = [
        {"label": "X", "job": "/p/a"},
        {"label": "X", "job": "/p/b"},
        {"label": "X [b]", "job": "/q/z"},
    ]
    pt.disambiguate_labels(systems)
    labels = [s["label"] for s in systems]
    check("no system was dropped", len(systems), 3)
    check("all labels unique", len(set(labels)), 3)


def test_reliability_is_reported_as_na_when_undefined():
    """Both coefficients are undefined on small or degenerate matrices, and must not raise.

    Spearman-Brown is 2r/(1+r): r = -1 divides by zero, and any r <= 0 puts the coefficient
    outside [0, 1). Both are reachable whenever a split has too few cases to correlate sensibly,
    which is exactly the shape a user hits by passing mismatched job dirs.
    """
    identical = [[1, 1, 1], [1, 1, 1]]
    check("cronbach identical rows", pt.cronbach_alpha(identical), None)
    check("split-half identical rows", pt.split_half(identical), None)
    for name, m in (
        ("one case", [[1], [0]]),
        ("no cases", [[], []]),
        (
            "two cases, opposed",
            [[1, 0], [0, 1]],
        ),  # split-half r = -1, formerly ZeroDivisionError
        ("sixteen systems, one case", [[i % 2] for i in range(16)]),
    ):
        check(f"cronbach {name}", pt.cronbach_alpha(m), None)
        check(f"split-half {name}", pt.split_half(m), None)

    # Alpha has no pole and is legitimately negative when items anti-correlate, so it is reported
    # rather than nulled; split-half on the same matrix has r = -0.5, which the guard drops.
    anti = [[1, 0], [0, 1], [1, 1]]
    check("cronbach anti-correlated", round(pt.cronbach_alpha(anti), 3), -2.0)
    check("split-half anti-correlated", pt.split_half(anti), None)


def test_tiers_handles_an_empty_ordering():
    check("empty tiers", len(pt.tiers([], [], "acc", "p_bh")), 0, 0)


def main() -> int:
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    if FAILS:
        for f in FAILS:
            print(f"FAIL {f}")
        print(f"\n{len(FAILS)} failure(s)")
        return 1
    print("all paired_tests checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
