#!/usr/bin/env python3
"""
Adds a new pane to a tmux window while keeping it laid out as a grid
capped at 2 rows, growing columns to the right, columns prioritized over
rows (see grid_layout.py for the exact rule). Creates the pane with a
single simple split, then atomically corrects the whole layout in one
more `select-layout` call -- at most 2 visible steps total (pane
creation is unavoidably visible), instead of the many break/join/resize
steps this used to take.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grid_layout


def main():
    win = sys.argv[1] if len(sys.argv) > 1 else grid_layout.tmux(
        "display-message", "-p", "#{window_id}"
    ).strip()

    panes = []
    for line in grid_layout.tmux(
        "list-panes", "-t", win, "-F", "#{pane_id} #{pane_left}"
    ).splitlines():
        pid, left = line.split()
        panes.append((pid, int(left)))

    n = len(panes)
    if n == 0:
        return

    if n % 2 == 0:
        # An odd total after adding -> fill the leftmost column that's
        # still only 1 row tall.
        from collections import Counter

        counts = Counter(left for _, left in panes)
        incomplete_left = min(left for _, left in panes if counts[left] == 1)
        target = next(pid for pid, left in panes if left == incomplete_left)
        grid_layout.tmux("split-window", "-v", "-t", target)
    else:
        # An even total after adding -> new column. Split whichever pane
        # is currently rightmost; apply_grid_layout corrects the exact
        # position/size right after.
        rightmost = max(panes, key=lambda p: p[1])[0]
        grid_layout.tmux("split-window", "-h", "-t", rightmost)

    grid_layout.apply_grid_layout(win)


if __name__ == "__main__":
    main()
