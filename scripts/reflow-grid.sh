#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grid_layout


def main():
    if sys.argv[1:] == ["--cache-all"]:
        grid_layout.cache_all_layouts()
        return
    win = sys.argv[1] if len(sys.argv) > 1 else grid_layout.tmux(
        "display-message", "-p", "#{window_id}"
    ).strip()
    grid_layout.apply_grid_layout(win, *sys.argv[2:])


if __name__ == "__main__":
    main()
