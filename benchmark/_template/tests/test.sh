#!/bin/bash
# Harbor verifier for MIMIC healthcare tasks.
#
# DETERMINISTIC-ONLY per the scoring section of the top-level README: no LLM call, no credentials,
# no network. Reads the agent's deliverable (/workspace/report.md) and the tool-call trajectory
# Harbor drops under /logs/agent/, normalizes the trajectory into verifier/evidence.jsonl
# (evidence.py), then scores the verdict + cited-ID grounding + the deterministic policy items
# (judge.py + rubrics.json) into reward.json.
#
# The LLM-judged metrics run OUTSIDE the trial, from these same persisted artifacts:
#   python benchmark/eval/grade.py jobs/<job>

set -u  # never set -e: we always want reward.json written

REPORT_FILE="/workspace/report.md"
REWARD_FILE="/logs/verifier/reward.json"
TESTS_DIR="$(dirname "$0")"

mkdir -p "$(dirname "$REWARD_FILE")"

# If the agent never produced a report, score 0 immediately (numeric-only dict).
if [ ! -f "$REPORT_FILE" ]; then
    echo '{"score": 0.0, "report_present": 0, "report_chars": 0}' > "$REWARD_FILE"
    echo "FAIL: $REPORT_FILE missing — agent produced no report" >&2
    exit 0
fi

# Persist the real report AND the rubric bundle into the trial logs, so an offline re-grade
# is fully self-contained (report + trajectory + the exact rubric used) — no need to
# regenerate rubrics.json from the task dir, which drifts if the rubric is later edited.
cp "$REPORT_FILE" "$(dirname "$REWARD_FILE")/report.md" 2>/dev/null || true
cp "$TESTS_DIR/rubrics.json" "$(dirname "$REWARD_FILE")/rubrics.json" 2>/dev/null || true

# Locate the agent trajectory if Harbor wrote one (ATIF trajectory.json is the
# canonical drop; the plain-text fallbacks cover other agent CLIs).
TRAJECTORY_FILE=""
for candidate in \
    /logs/agent/trajectory.json \
    /logs/agent/output.txt \
    /logs/agent/stdout.txt \
    /logs/agent/trajectory.txt; do
    if [ -f "$candidate" ]; then
        TRAJECTORY_FILE="$candidate"
        break
    fi
done

# Normalize the trajectory into evidence.jsonl BEFORE judging. This is where "what did the agent
# actually see" is extracted, while the native trajectory is still in front of us: the
# deterministic grounding metrics (cited-ID grounding, retrieval coverage) and the tool-call
# health counts are computed from it, and every offline consumer reads it instead of re-parsing
# per-harness trajectory dialects. Stdlib-only, no creds, no LLM — see evidence.py.
# Best-effort: a failure here must not cost the trial its reward.
EVIDENCE_FILE="$(dirname "$REWARD_FILE")/evidence.jsonl"
if [ -n "$TRAJECTORY_FILE" ]; then
    python3 "$TESTS_DIR/evidence.py" \
        --trajectory "$TRAJECTORY_FILE" \
        --output "$EVIDENCE_FILE" \
        --summary "$(dirname "$REWARD_FILE")/evidence_summary.json" \
        || echo "[test] evidence.py failed — deterministic grounding metrics will be skipped" >&2
fi

# No third-party dep guard needed: this verifier is deterministic-only
# (the scoring section of the top-level README), so nothing here imports `openai`. That also means the verify
# step needs no network.

python3 "$TESTS_DIR/judge.py" \
    --report-file "$REPORT_FILE" \
    --rubrics-file "$TESTS_DIR/rubrics.json" \
    --trajectory-file "$TRAJECTORY_FILE" \
    --evidence-file "$EVIDENCE_FILE" \
    --output "$REWARD_FILE"

# Fallback: judge.py writes reward.json under its own always-write contract, but if Python
# fails to even start (import crash, half-done pip install, exec/permission error) nothing is
# written and Harbor would see an empty verifier dir — worse than a judge_failed reward.
[ -f "$REWARD_FILE" ] || echo '{"score": 0.0, "judge_failed": 1, "judge_launch_failed": 1}' > "$REWARD_FILE"

# Exit clean either way — Harbor reads the reward file, not the exit code.
exit 0
