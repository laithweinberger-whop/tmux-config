#!/usr/bin/env python3
import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import statistics
import struct
import subprocess
import tempfile
import termios
import threading
import time


class Tmux:
    def __init__(self, repo, windows):
        self.temp = tempfile.TemporaryDirectory(prefix="tmux-benchmark-")
        self.root = Path(self.temp.name)
        self.socket = str(self.root / "socket")
        self.buffer = b""
        self.terminal_output = bytearray()
        self.env = dict(os.environ, TERM="xterm-256color", HOME=str(self.root))
        self.env.pop("TMUX", None)
        subprocess.run([
            "tmux", "-S", self.socket, "-f", "/dev/null", "new-session", "-d",
            "-s", "bench", "-x", "220", "-y", "64", "/bin/cat",
        ], env=self.env, check=True)
        self.control = subprocess.Popen(
            ["tmux", "-S", self.socket, "-C", "attach-session", "-t", "bench"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self.env,
        )
        while not self.line().startswith("%end "):
            pass
        self.cmd("refresh-client -C 220,64")
        self.cmd("set -g default-shell /bin/sh")
        self.cmd("set -g default-command /bin/cat")
        self.cmd("set -g mouse on")
        self.cmd("set -s escape-time 0")
        for w in range(windows):
            if w:
                self.cmd("new-window -d -t bench: /bin/cat")
            for _ in range(3):
                self.cmd(f"split-window -dh -t @{w} /bin/cat")
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 64, 220, 0, 0))
        self.terminal = subprocess.Popen(
            ["tmux", "-S", self.socket, "attach-session", "-t", "bench"],
            stdin=slave, stdout=slave, stderr=slave, env=self.env,
        )
        os.close(slave)
        self.reader = threading.Thread(target=self.drain, daemon=True)
        self.reader.start()
        self.wait(lambda: "/dev/" in self.cmd("list-clients -F '#{client_name}'"))
        shutil.copytree(repo / "scripts", self.root / ".tmux/scripts")
        shutil.copytree(repo / "smux", self.root / ".smux")
        config = "\n".join(
            line for line in (repo / "tmux.conf").read_text().splitlines()
            if "autosave-loop" not in line and "~/.tmux/plugins/tpm/tpm" not in line
        ).replace("~/.tmux", str(self.root / ".tmux")).replace("~/.smux", str(self.root / ".smux"))
        (self.root / "tmux.conf").write_text(config)
        self.cmd("source-file " + shlex.quote(str(self.root / "tmux.conf")))
        self.wait(lambda: self.cmd("display -p '#{E:@grid_layout}'"), timeout=30)
        for w in range(windows):
            self.cmd(f"run-shell -C -t @{w} '#{{E:@grid_reflow}}'")
        self.wait(lambda: not self.cmd("show-messages -J"), timeout=30)

    def line(self):
        while b"\n" not in self.buffer:
            if not select.select([self.control.stdout], [], [], 30)[0]:
                raise TimeoutError("tmux control response")
            data = os.read(self.control.stdout.fileno(), 65536)
            if not data:
                raise RuntimeError("tmux control connection closed")
            self.buffer += data
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.decode()

    def cmd(self, command):
        marker = "__benchmark_done_" + str(time.perf_counter_ns())
        self.control.stdin.write((command + "\ndisplay -p " + marker + "\n").encode())
        self.control.stdin.flush()
        rows = []
        in_response = False
        done = False
        errors = []
        while True:
            line = self.line()
            if line.startswith("%begin "):
                in_response = True
            elif line.startswith("%error "):
                errors.append(rows[:])
                in_response = False
            elif line.startswith("%end "):
                in_response = False
                if done:
                    if errors:
                        raise AssertionError((command, errors))
                    return "\n".join(rows)
            elif line == marker:
                done = True
            elif in_response:
                rows.append(line)

    def drain(self):
        while True:
            try:
                self.terminal_output.extend(os.read(self.master, 65536))
            except OSError:
                return

    def wait(self, predicate, timeout=10):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            result = predicate()
            if result:
                return result
            time.sleep(0.001)
        raise AssertionError("Timed out waiting for tmux state; selection=" + self.selection() + "; panes=" + repr(self.panes()))

    def panes(self, window="@0"):
        return [row.split() for row in self.cmd(
            f"list-panes -t {window} -F '#{{pane_id}} #{{pane_left}} #{{pane_top}} #{{pane_width}} #{{pane_height}}'"
        ).splitlines()]

    def selection(self):
        return self.cmd("display -p '#{@swap_sel_1}|#{@swap_sel_2}'")

    def mouse(self, pane, shift=True):
        _, left, top, *_ = pane
        x, y = int(left) + 2, int(top) + 2
        button = 4 if shift else 0
        os.write(self.master, f"\x1b[<{button};{x};{y}M\x1b[<{button};{x};{y}m".encode())

    def key(self, key):
        os.write(self.master, b"\x1b" + key.encode())

    def grid(self, window="@0"):
        panes = self.panes(window)
        columns = {}
        for pane, left, top, width, height in panes:
            columns.setdefault(int(left), []).append((pane, int(top), int(width), int(height)))
        widths = [column[0][2] for column in columns.values()]
        expected_columns = 1 if len(panes) == 1 else len(panes) // 2 + 1
        if len(columns) != expected_columns or max(widths) - min(widths) > 1:
            return False
        counts = [len(column) for _, column in sorted(columns.items())]
        paired = len(panes) - expected_columns
        return counts == [2] * paired + [1] * (expected_columns - paired)

    def close(self):
        subprocess.run(["tmux", "-S", self.socket, "kill-server"], env=self.env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.control.wait(timeout=10)
        self.terminal.wait(timeout=10)
        os.close(self.master)
        self.reader.join(timeout=1)
        self.temp.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--windows", type=int, default=25)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    tmux = Tmux(Path(__file__).resolve().parents[1], args.windows)
    samples = {}

    def record(name, action, complete):
        start = time.perf_counter()
        action()
        tmux.wait(complete)
        samples.setdefault(name, []).append((time.perf_counter() - start) * 1000)

    try:
        for _ in range(args.rounds):
            panes = tmux.panes()
            record("shift_select", lambda: tmux.mouse(panes[0]),
                   lambda: tmux.selection() == panes[0][0] + "|")
            assert tmux.cmd(f"display -p -t {panes[0][0]} '#{{E:pane-border-style}}'") == "fg=yellow"
            record("shift_select_second", lambda: tmux.mouse(panes[1]),
                   lambda: tmux.selection() == panes[0][0] + "|" + panes[1][0])
            record("swap", lambda: tmux.key("x"), lambda: tmux.selection() == "|")
            assert [p[0] for p in tmux.panes()][:2] == [panes[1][0], panes[0][0]]
            panes = tmux.panes()
            tmux.mouse(panes[0])
            tmux.wait(lambda: tmux.selection() == panes[0][0] + "|")
            record("plain_click_clear", lambda: tmux.mouse(panes[1], False),
                   lambda: tmux.selection() == "|")
            record("split", lambda: tmux.key("n"),
                   lambda: len(tmux.panes()) == 5 and tmux.grid())
            victim = tmux.panes()[2][0]
            record("close_and_reflow", lambda: tmux.cmd("kill-pane -t " + victim),
                   lambda: len(tmux.panes()) == 4 and tmux.grid())
        panes = tmux.panes()
        for pane, expected in [(panes[0], panes[0][0] + "|"),
                               (panes[1], panes[0][0] + "|" + panes[1][0]),
                               (panes[2], panes[2][0] + "|"),
                               (panes[2], "|")]:
            tmux.mouse(pane)
            tmux.wait(lambda: tmux.selection() == expected)
        tmux.cmd("bind-key -n F12 set-option -g @benchmark_done 1")
        for _ in range(10):
            tmux.cmd("set-option -g @benchmark_done 0")
            def burst():
                for _ in range(101):
                    tmux.mouse(panes[0])
                os.write(tmux.master, b"\x1b[24~")
            record("burst_101_shift_clicks", burst,
                   lambda: tmux.cmd("show -gqv @benchmark_done") == "1")
            assert tmux.selection() == panes[0][0] + "|"
            tmux.mouse(panes[0], False)
            tmux.wait(lambda: tmux.selection() == "|")
        assert not tmux.cmd("show-messages -J"), "Warm operations spawned shell jobs"
        snapshots = tmux.cmd("list-windows -a -F '#{window_id} #{window_layout}'")
        for w in range(1, args.windows):
            victim = tmux.panes(f"@{w}")[1][0]
            record("background_window_close", lambda: tmux.cmd("kill-pane -t " + victim),
                   lambda: tmux.grid(f"@{w}"))
        assert tmux.cmd("display -p '#{window_id}'") == "@0"
        assert tmux.cmd("display -p -t @0 '#{window_layout}'") == snapshots.splitlines()[0].split(" ", 1)[1]
        for _ in range(30):
            tmux.key("n")
            tmux.wait(lambda: len(tmux.panes()) == 5 and tmux.grid())
            victim = tmux.panes()[2][0]
            record("process_exit_and_reflow", lambda: tmux.cmd("send-keys -t " + victim + " C-d"),
                   lambda: len(tmux.panes()) == 4 and tmux.grid())
        for size in [(201, 55), (180, 48), (219, 63)]:
            tmux.cmd(f"resize-window -t @0 -x {size[0]} -y {size[1]}")
            victim = tmux.panes()[1][0]
            record("uncached_size_close", lambda: tmux.cmd("kill-pane -t " + victim),
                   lambda: len(tmux.panes()) == 3 and tmux.grid())
            tmux.key("n")
            tmux.wait(lambda: len(tmux.panes()) == 4 and tmux.grid())
        for _ in range(25):
            tmux.key("n")
            tmux.wait(lambda: len(tmux.panes()) == 5 and tmux.grid())
            record("keyboard_close_and_reflow", lambda: tmux.key("w"),
                   lambda: len(tmux.panes()) == 4 and tmux.grid())
        tmux.cmd("set-window-option -t @0 pane-base-index 1")
        tmux.key("n")
        tmux.wait(lambda: len(tmux.panes()) == 5 and tmux.grid())
        tmux.key("w")
        tmux.wait(lambda: len(tmux.panes()) == 4 and tmux.grid())
        tmux.cmd("set-window-option -t @0 pane-base-index 0")
        panes = tmux.panes()
        tmux.mouse(panes[0])
        tmux.wait(lambda: tmux.selection() == panes[0][0] + "|")
        tmux.mouse(panes[1])
        tmux.wait(lambda: tmux.selection() == panes[0][0] + "|" + panes[1][0])
        tmux.cmd("kill-pane -t " + panes[1][0])
        tmux.wait(lambda: len(tmux.panes()) == 3 and tmux.grid())
        tmux.key("x")
        tmux.wait(lambda: tmux.selection() == "|")
        tmux.key("n")
        tmux.wait(lambda: len(tmux.panes()) == 4 and tmux.grid())
        tmux.cmd("source-file " + shlex.quote(str(tmux.root / "tmux.conf")))
        tmux.wait(lambda: not tmux.cmd("show-messages -J"), timeout=30)
        snapshot = tmux.cmd("display -p -t @0 '#{window_layout}'")
        last = tmux.cmd("new-window -d -P -F '#{pane_id}' /bin/cat")
        tmux.cmd("kill-pane -t " + last)
        assert tmux.cmd("display -p -t @0 '#{window_layout}'") == snapshot
        print("Functional checks passed", flush=True)
    finally:
        tmux.close()
        for name, values in samples.items():
            ordered = sorted(values)
            print(f"{name}: n={len(values)} median={statistics.median(values):.3f}ms "
                  f"p95={ordered[math.ceil(len(values)*.95)-1]:.3f}ms max={max(values):.3f}ms", flush=True)
        if args.output:
            args.output.write_text(json.dumps(samples, indent=2) + "\n")


if __name__ == "__main__":
    main()
