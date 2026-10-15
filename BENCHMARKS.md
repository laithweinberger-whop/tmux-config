# Pane latency verification

Tested on macOS with tmux 3.7c. The isolated benchmark starts its own socket,
25 windows and 100 panes, and disables persistence plugins. It injects mouse
and keyboard input through a pseudo-terminal and waits for the resulting tmux
state through a persistent control connection. Timings include that observation
round trip; they do not measure the terminal emulator's display refresh.

| Operation | Samples | Median | 95th percentile |
| --- | ---: | ---: | ---: |
| shift select | 200 | 3.29 ms | 4.16 ms |
| shift select second | 200 | 3.28 ms | 4.28 ms |
| swap | 200 | 3.22 ms | 3.87 ms |
| plain click clear | 200 | 1.22 ms | 3.03 ms |
| split | 200 | 4.69 ms | 6.62 ms |
| close and reflow | 200 | 2.50 ms | 4.04 ms |
| burst 101 shift clicks | 10 | 38.83 ms | 43.01 ms |
| background window close | 24 | 1.31 ms | 1.46 ms |
| process exit and reflow | 30 | 3.38 ms | 29.29 ms |
| uncached size close | 3 | 950.80 ms | 1023.74 ms |
| keyboard close and reflow | 25 | 2.82 ms | 3.26 ms |

The original scripts took a median 538 ms for a plain click with no selection,
1,723 ms for a Shift-click, and 42,884 ms for a full reflow across 25 windows
(50, 50 and 10 samples respectively). Those baseline timings run the original
scripts directly; the updated measurements exercise the real bindings/hooks.

Ordinary selection, swapping, splitting and closing use native tmux commands.
Layouts for up to 32 panes are cached for each window size at load time. A new
size or larger pane count invokes Python once to extend the cache. Python 3
must be available on PATH.

The checks cover selection toggling, third-pane replacement, rapid clicks,
background-window closes, process exits, resized windows, keyboard closes,
nonzero pane numbering, closing a selected pane, config reloads and closing
a window's final pane. Additional checks exercised cross-window swaps, manual
sizing, growth to 34 panes, and closing a window while its cache was building.

```sh
python3 tests/benchmark.py --rounds 200 --output /tmp/tmux-benchmark-results.json
```
