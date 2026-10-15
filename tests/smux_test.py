#!/usr/bin/env python3
import argparse
import json
import os
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CLI = REPO / "smux/bin/smux"


class Server:
    def __init__(self, root, name):
        self.socket = str(root / name)
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "main", "-x", "220", "-y", "64", "/bin/cat")
        self.tmux("set", "-g", "default-shell", "/bin/sh")
        self.tmux("set", "-g", "default-command", "/bin/cat")
        self.env = dict(os.environ, HOME=str(root), TMUX=self.socket + "," + self.tmux("display", "-p", "#{pid}") + ",0", TMUX_PANE="%0")
        self.env.pop("TMUX_BRIDGE_SOCKET", None)

    def tmux(self, *args):
        return subprocess.check_output(["tmux", "-S", self.socket, *args], text=True).strip()

    def cli(self, *args, env=None, ok=True):
        result = subprocess.run([str(CLI), *args], env=env or self.env, capture_output=True, text=True, check=False)
        assert (result.returncode == 0) == ok, (args, result.stdout, result.stderr)
        return result.stdout.strip() if ok else result.stderr

    def panes(self):
        return dict(row.split() for row in self.tmux("list-panes", "-a", "-F", "#{pane_id} #{pane_pid}").splitlines())

    def shell_works(self, pane):
        marker = "shell_ready_" + str(time.monotonic_ns())
        self.tmux("send-keys", "-t", pane, "-l", "printf '%s%s\\n' 'shell_ready_' '" + marker.removeprefix("shell_ready_") + "'")
        self.tmux("send-keys", "-t", pane, "Enter")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            lines = self.tmux("capture-pane", "-p", "-t", pane).splitlines()
            if marker in lines:
                return
            time.sleep(.01)
        raise AssertionError((pane, lines))


def regressions(a, b, root):
    a.tmux("new-window", "-t", "main:", "/bin/cat")
    a.tmux("new-session", "-d", "-s", "unrelated", "/bin/cat")
    original = a.panes()
    windows = a.tmux("list-windows", "-a", "-F", "#{session_id} #{window_id} #{window_index}")
    a.tmux("set", "-p", "-t", "%0", "@name", "worker")
    a.tmux("set", "-p", "-t", "%1", "@name", "worker")
    a.tmux("set", "-p", "-t", "%2", "@name", "worker")
    assert a.cli("resolve", "worker") == "%0"
    assert a.cli("resolve", "main:0.0") == "%0"
    assert a.cli("resolve", "0") == "%0"
    assert "%1" not in a.cli("list")
    assert "%1" in a.cli("list", "--all")
    a.cli("resolve", "main", ok=False)
    a.cli("resolve", "%99999", ok=False)
    for env in (dict(a.env, TMUX=""), dict(a.env, TMUX_PANE="%99999"),
                dict(a.env, TMUX=a.socket + ",1,0"), dict(a.env, TMUX_BRIDGE_SOCKET=str(root / "missing"))):
        a.cli("pane", env=env, ok=False)
    assert a.cli("--socket", a.socket, "--from", "%0", "id", env=dict(a.env, TMUX="", TMUX_PANE="")) == "%0"
    child = json.loads(a.cli("pane", "--", "/bin/sleep", "30"))
    assert child["window"] == "@0" and child["session"] == "$0"
    pane = child["pane"]
    assert a.tmux("display", "-p", "-t", "main:", "#{window_id} #{pane_id}") == "@0 " + pane
    assert a.tmux("display", "-p", "-t", "unrelated:", "#{window_id}") == "@2"
    a.cli("name", pane, "worker", ok=False)
    a.tmux("set", "-p", "-t", pane, "@name", "worker")
    a.cli("resolve", "worker", ok=False)
    a.cli("name", pane, "review.worker")
    assert a.cli("resolve", "review.worker") == pane
    for target in ("%0", "%1", "%2", "main", "@0", "review.worker"):
        a.cli("stop", target, ok=False)
        a.cli("close", target, ok=False)
    a.cli("stop", pane, env=dict(a.env, TMUX_PANE="%1"), ok=False)
    old_pid = a.panes()[pane]
    children = subprocess.run(["pgrep", "-P", old_pid], capture_output=True, text=True, check=False).stdout.split()
    a.cli("read", pane)
    a.cli("stop", pane)
    assert a.panes()[pane] != old_pid
    a.cli("type", pane, "read belonged to old process", ok=False)
    a.shell_works(pane)
    for pid in [old_pid, *children]:
        assert subprocess.run(["ps", "-p", pid], capture_output=True, check=False).returncode != 0, ("surviving stopped process", pid)
    a.cli("close", pane)
    assert a.panes() == original

    for mode in ("pane", "window"):
        child = json.loads(a.cli(mode, "--", "/bin/sh", "-c", "printf 'command_done\\n'"))
        pane = child["pane"]
        assert (child["window"] == "@0") == (mode == "pane")
        a.shell_works(pane)
        assert "command_done" in a.tmux("capture-pane", "-p", "-t", pane)
        a.cli("close", pane)
        assert a.panes() == original
        assert a.tmux("list-windows", "-a", "-F", "#{session_id} #{window_id} #{window_index}") == windows

    child = json.loads(a.cli("pane", "--", "/bin/sleep", "30"))["pane"]
    time.sleep(.1)
    a.tmux("send-keys", "-t", child, "C-c")
    a.shell_works(child)
    a.cli("close", child)
    child = json.loads(a.cli("pane", "--", "smux-command-that-does-not-exist"))["pane"]
    a.shell_works(child)
    a.cli("close", child)

    a.tmux("resize-pane", "-Z", "-t", "%0")
    child = json.loads(a.cli("pane"))["pane"]
    assert a.tmux("display", "-p", "-t", child, "#{window_zoomed_flag} #{pane_active}") == "0 1"
    a.cli("close", child)

    a.cli("read", "%1")
    a.cli("type", "%1", "wrong caller", env=dict(a.env, TMUX_PANE="%2"), ok=False)
    a.cli("read", "%0")
    b.cli("type", "%0", "wrong server", ok=False)
    a.cli("message", "%1", "one message")
    a.cli("keys", "%1", "Enter", ok=False)
    a.cli("read", "%1")
    a.cli("keys", "%1", "Enter")
    captured = a.tmux("capture-pane", "-p", "-t", "%1")
    assert "[tmux-bridge from:worker pane:%0] one message" in captured
    assert "wrong caller" not in captured
    a.cli("read", "%1")
    a.cli("type", "%1", "literal;")
    assert "literal;" in a.tmux("capture-pane", "-p", "-t", "%1")
    a.cli("read", "%1")
    for path in (root / ".cache/smux/reads").iterdir():
        os.utime(path, (0, 0))
    a.cli("type", "%1", "stale read", ok=False)

    outfile = root / "argv.json"
    values = ["#{pane_id}", ";", "a'b", "$(printf should_not_run)", "two words", "line\nbreak"]
    child = json.loads(a.cli("pane", "--", "/usr/bin/python3", "-c",
                            "import sys,json;open(sys.argv[1],'w').write(json.dumps(sys.argv[2:]))",
                            str(outfile), *values))["pane"]
    a.shell_works(child)
    assert json.loads(outfile.read_text()) == values
    a.cli("close", child)
    assert a.panes() == original
    assert set(b.panes()) == {"%0"}

    executable = root / "smux-path-probe"
    executable.write_text("#!/bin/sh\nprintf 'path_probe_ok\\n'\npwd\n")
    executable.chmod(0o755)
    child = json.loads(a.cli("pane", "--cwd", str(root), "--", executable.name,
                            env=dict(a.env, PATH=str(root) + os.pathsep + a.env["PATH"])))["pane"]
    a.shell_works(child)
    captured = a.tmux("capture-pane", "-p", "-t", child)
    assert "path_probe_ok" in captured and str(root) in captured
    a.cli("close", child)
    print("Regression scenarios passed; original panes/processes and second server preserved.", flush=True)


def timed(a, rounds):
    samples = {name: [] for name in ("resolve", "pane", "stop", "close", "window")}
    for _ in range(rounds):
        start = time.perf_counter()
        a.cli("resolve", "%0")
        samples["resolve"].append((time.perf_counter() - start) * 1000)
        for mode in ("pane", "window"):
            start = time.perf_counter()
            child = json.loads(a.cli(mode, "--", "/bin/sleep", "30"))["pane"]
            samples[mode].append((time.perf_counter() - start) * 1000)
            for action in ("stop", "close"):
                start = time.perf_counter()
                a.cli(action, child)
                samples[action].append((time.perf_counter() - start) * 1000)
    for name, times in samples.items():
        ordered = sorted(times)
        print(f"{name}: n={len(times)} median={statistics.median(times):.2f}ms p95={ordered[int((len(times)-1)*.95)]:.2f}ms max={max(times):.2f}ms", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=20)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="smux-tests-") as directory:
        root = Path(directory)
        a, b = Server(root, "a"), Server(root, "b")
        try:
            regressions(a, b, root)
            timed(a, args.rounds)
        finally:
            a.tmux("kill-server")
            b.tmux("kill-server")


if __name__ == "__main__":
    main()
