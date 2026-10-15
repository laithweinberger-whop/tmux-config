#!/usr/bin/env python3
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("agent_sessions", Path(__file__).resolve().parents[1] / "scripts/agent-sessions.py")
sessions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sessions)

processes = {
    10: (1, "shell-start", "zsh"),
    20: (10, "agent-start", "codex"),
    25: (20, "server-start", "codex-app-server"),
    30: (25, "hook-start", "sh"),
    40: (30, "python-start", "python3"),
    50: (1, "other-shell-start", "zsh"),
    60: (50, "other-agent-start", "claude"),
    70: (60, "other-hook-start", "python3"),
    80: (20, "nested-agent-start", "claude"),
    90: (80, "nested-hook-start", "python3"),
}
assert sessions.owner(processes, {10: "%1", 50: "%2"}, 40, "codex") == ("%1", 20, "agent-start")
assert sessions.owner(processes, {10: "%1", 50: "%2"}, 70, "claude") == ("%2", 60, "other-agent-start")
assert sessions.owner(processes, {50: "%2"}, 40, "codex") is None
assert sessions.owner(processes, {10: "%1"}, 90, "claude") is None

snapshot = "\n".join([
    "pane\treview\t0\t1\t:*\t1\tfirst\t:/same/cwd\t1\tcodex\t:codex --yolo",
    "pane\treview\t0\t1\t:*\t0\tsecond\t:/same/cwd\t0\tclaude\t:claude",
    "window\treview\t0\t:review\t1\t:*\tlayout",
]) + "\n"
records = {
    ("review", "0", "1"): {"agent": "codex", "session_id": "id-one", "pid": 20, "started": "agent-start"},
    ("review", "0", "0"): {"agent": "claude", "session_id": "id-two", "pid": 60, "started": "other-agent-start"},
}
restored = sessions.rewrite_snapshot(snapshot, records, processes)
assert "\tcodex\t:cod resume id-one --no-daemon\n" in restored
assert "\tclaude\t:cla --resume id-two\n" in restored
assert restored.splitlines()[2] == snapshot.splitlines()[2]
assert sessions.rewrite_snapshot(snapshot, records, {}) == snapshot
assert sessions.rewrite_snapshot(snapshot, records, {20: (10, "reused-pid", "codex")}) == snapshot
assert sessions.rewrite_snapshot(snapshot, {}, processes) == snapshot
records[("review", "0", "1")]["session_id"] = "$(touch not-allowed)"
assert "cod resume $(" not in sessions.rewrite_snapshot(snapshot, records, processes)
print("Exact per-pane IDs, shared directories, reordered panes, stale PIDs, and ambiguous ownership passed.")
