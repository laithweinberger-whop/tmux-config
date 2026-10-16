#!/usr/bin/env python3
import subprocess
import sys


def main():
    socket, session, pane = sys.argv[1:]

    def tmux(*args):
        return subprocess.check_output(["tmux", "-S", socket, *args], text=True).strip()

    windows = [row.split("\t", 1) for row in tmux(
        "list-windows", "-t", session, "-F", "#{window_id}\t#{window_name}").splitlines()]
    destinations = [window for window, name in windows if name == "minimized"]
    source, count, cwd = tmux("display-message", "-p", "-t", pane,
                              "#{window_id}\t#{window_panes}\t#{pane_current_path}").split("\t", 2)
    if source not in [window for window, _ in windows]:
        raise ValueError("pane no longer belongs to the selected session")
    if source in destinations:
        return
    if len(destinations) > 1:
        raise ValueError("multiple windows are named minimized; rename one before minimizing")
    if count == "1":
        tmux("split-window", "-d", "-h", "-t", pane, "-c", cwd)
    if destinations:
        destination = destinations[0]
        tmux("join-pane", "-d", "-h", "-f", "-s", pane, "-t", session + ":" + destination)
    else:
        destination = tmux("break-pane", "-d", "-P", "-F", "#{window_id}", "-n", "minimized",
                           "-s", pane, "-t", session + ":")
    tmux("set-option", "-w", "-t", destination, "automatic-rename", "off")
    for window in (source, destination):
        if tmux("show-option", "-gqv", "@grid_reflow"):
            tmux("run-shell", "-C", "-t", window, "#{E:@grid_reflow}")
        else:
            tmux("select-layout", "-t", window, "tiled")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Could not minimize pane: {error}", file=sys.stderr)
        sys.exit(1)
