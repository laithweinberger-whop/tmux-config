#!/usr/bin/env python3
"""
Rebuilds a window's pane layout into the capped 2-row grid, growing
columns to the right, columns prioritized over rows. Applies the whole
target layout as a SINGLE atomic `select-layout` call (see
grid_layout.py) so there's exactly one redraw -- no visible intermediate
rearrangement, and no pane is ever broken out/killed/recreated.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grid_layout


def main():
    win = sys.argv[1] if len(sys.argv) > 1 else grid_layout.tmux(
        "display-message", "-p", "#{window_id}"
    ).strip()
    grid_layout.apply_grid_layout(win)


if __name__ == "__main__":
    main()
