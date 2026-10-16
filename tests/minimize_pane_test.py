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
        server.wait(lambda: server.cmd(f"display -p -t {pane} '#{{window_name}}'") == "Minimized")
        windows = server.cmd("list-windows -t bench -F '#{window_name}'").splitlines()
        assert windows.count("Minimized") == 1, windows
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
    server.cmd(f"rename-window -t {source} 'Renamed main'")
    for index, pane in enumerate(panes):
        server.cmd(f"select-window -t {destination}")
        server.cmd(f"select-pane -t {pane}")
        assert server.cmd(f"show-option -pqv -t {pane} @smux_restore_window") == source
        server.key("+" if index % 2 == 0 else "=")
        server.wait(lambda: server.cmd(f"display -p -t {pane} '#{{window_id}}'") == source)
        server.wait(lambda: server.cmd("display -p -t bench: '#{pane_id}'") == pane)
        server.wait(lambda: server.cmd(f"show-option -pqv -t {pane} @smux_restore_window") == "")
        server.wait(lambda: server.grid(source))
    assert "Minimized" not in server.cmd("list-windows -t bench -F '#{window_name}'").splitlines()
    server.cmd("new-window -n scratch /bin/cat")
    scratch = server.cmd("display -p '#{window_id}'")
    scratch_pane = server.cmd("display -p '#{pane_id}'")
    scratch_pid = server.cmd(f"display -p -t {scratch_pane} '#{{pane_pid}}'")
    server.key("-")
    server.wait(lambda: server.cmd(f"display -p -t {scratch_pane} '#{{window_name}}'") == "Minimized")
    assert server.cmd(f"show-option -pqv -t {scratch_pane} @smux_restore_window") == scratch
    server.cmd(f"kill-window -t {scratch}")
    server.cmd(f"select-window -t {scratch_pane}")
    server.key("+")
    server.wait(lambda: server.cmd(f"display -p -t {scratch_pane} '#{{window_name}}'") == "scratch")
    assert server.cmd(f"display -p -t {scratch_pane} '#{{pane_pid}}'") == scratch_pid
    server.cmd("new-session -d -s other /bin/cat")
    other = server.cmd("display -p -t other: '#{pane_id}'")
    terminal = next(client for client in server.cmd("list-clients -F '#{client_name}'").splitlines()
                    if client.startswith("/dev/"))
    server.cmd(f"switch-client -c {terminal} -t other")
    server.key("-")
    server.wait(lambda: server.cmd(f"display -p -t {other} '#{{window_name}}'") == "Minimized")
    assert server.cmd(f"display -p -t {other} '#{{session_name}}'") == "other"
    assert "Minimized" not in server.cmd("list-windows -t bench -F '#{window_name}'").splitlines()
    current = dict(row.split() for row in server.cmd("list-panes -a -F '#{pane_id} #{pane_pid}'").splitlines())
    assert all(current.get(pane) == pid for pane, pid in original.items())
    print("Minimize/restore shortcuts passed: original window saved, renamed/closed origins, both plus keys, empty collection removed, creation/reuse, focus, zoom, grid reflow, last-pane replacement, no-op in minimized, session isolation, and process preservation.")
finally:
    server.close()
