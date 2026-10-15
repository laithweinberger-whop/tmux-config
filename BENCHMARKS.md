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

## Smux verification

The smux regression suite uses two private tmux servers with overlapping `%N`
IDs, multiple sessions, duplicate labels, and an active window different from
the caller's. It verifies scoped resolution, fail-closed stale context, caller
ownership, zoomed-pane creation, separate window creation without changing
existing window indexes, working directory/PATH propagation, argument fidelity,
read-guard isolation/expiry, and shell recovery after normal exit, Ctrl-C,
missing executables, and explicit stop. Unrelated pane IDs and process IDs must
remain identical. Installer tests cover backups, both config paths, CLI and skill
symlinks, and repeat installation.

Final 20-round run on macOS/tmux 3.7c (140 samples). These are full CLI wall times,
including interpreter and tmux client startup, on a machine running other agents;
they are not native key-binding latency or agent/model startup time.

| Operation | Samples | Median | 95th percentile |
| --- | ---: | ---: | ---: |
| resolve | 20 | 530.21 ms | 1333.00 ms |
| create pane | 20 | 1010.05 ms | 1866.50 ms |
| stop into shell | 40 | 795.13 ms | 1595.74 ms |
| close child pane | 40 | 781.59 ms | 1596.23 ms |
| create window | 20 | 1044.95 ms | 1869.62 ms |

On a separate 20-pane fixture, the installed old bridge's `list` took a median
5,828.60 ms over 3 samples; the new `list --all` took 578.30 ms over 10 samples.
The old command launched process-inspection tools for each pane; the new one
uses tmux's own pane metadata in one snapshot. Earlier regression/timing runs
also passed, including another 140 CLI samples and a 21-sample smoke run.

With the smux base config included, the existing 25-window/100-pane UI benchmark
passed another 392 samples. Median Shift-selection was 2.79 ms, split 3.78 ms,
close/reflow 2.00 ms, and keyboard close 2.45 ms. First use of an uncached size
still incurs Python startup (median 568.41 ms in this run). A separate integration
check ran five pane and five window create/stop/close cycles with the real grid
hooks and a PTY client, preserving all 12 original pane processes.

The local installer was also applied to the running server without restarting
it; all 53 existing pane IDs and process IDs were preserved.

```sh
python3 tests/smux_test.py --rounds 20
python3 tests/install_test.py
python3 tests/benchmark.py --rounds 50 --windows 25
```
