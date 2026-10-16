#!/usr/bin/env python3
import os
from pathlib import Path
from benchmark import Tmux


server = Tmux(Path(__file__).resolve().parents[1], 1)
try:
    original = dict(row.split() for row in server.cmd("list-panes -a -F '#{pane_id} #{pane_pid}'").splitlines())
    source = "@0"
    panes = [row[0] for row in server.panes(source)]
    for index, pane in enumerate(panes):
        server.cmd(f"select-pane -t {pane}")
        if index == 0:
            server.cmd(f"resize-pane -Z -t {pane}")
        server.key("-")
        server.wait(lambda: server.cmd(f"display -p -t {pane} '#{{window_name}}'") == "minimized")
        windows = server.cmd("list-windows -t bench -F '#{window_name}'").splitlines()
        assert windows.count("minimized") == 1, windows
        destination = server.cmd(f"display -p -t {pane} '#{{window_id}}'")
        assert destination != source
        assert server.cmd("display -p -t bench: '#{window_id}'") == source
        server.wait(lambda: server.grid(source) and server.grid(destination))
        assert len(server.panes(destination)) == index + 1
        assert server.cmd(f"display -p -t {pane} '#{{pane_pid}}'") == original[pane]
    assert len(server.panes(source)) == 1
    assert server.panes(source)[0][0] not in original
    server.cmd(f"select-window -t {destination}")
    state = server.cmd("list-panes -a -F '#{window_id} #{pane_id} #{pane_pid}'")
    server.key("-")
    server.cmd("bind-key -n F12 set-option -g @minimize_test_done 1")
    os.write(server.master, b"\x1b[24~")
    server.wait(lambda: server.cmd("show-option -gqv @minimize_test_done") == "1")
    assert server.cmd("list-panes -a -F '#{window_id} #{pane_id} #{pane_pid}'") == state
    server.cmd("new-session -d -s other /bin/cat")
    other = server.cmd("display -p -t other: '#{pane_id}'")
    terminal = next(client for client in server.cmd("list-clients -F '#{client_name}'").splitlines()
                    if client.startswith("/dev/"))
    server.cmd(f"switch-client -c {terminal} -t other")
    server.key("-")
    server.wait(lambda: server.cmd(f"display -p -t {other} '#{{window_name}}'") == "minimized")
    assert server.cmd(f"display -p -t {other} '#{{session_name}}'") == "other"
    assert len(server.panes(destination)) == len(panes)
    current = dict(row.split() for row in server.cmd("list-panes -a -F '#{pane_id} #{pane_pid}'").splitlines())
    assert all(current.get(pane) == pid for pane, pid in original.items())
    print("Option-minus passed: creation/reuse, focus, zoom, grid reflow, last-pane replacement, no-op in minimized, session isolation, and process preservation.")
finally:
    server.close()
