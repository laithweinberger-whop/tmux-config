"""
Shared logic for laying out panes in a grid capped at 2 rows, growing
columns to the right, columns prioritized over rows (every even-numbered
pane opens a new column; every odd-numbered pane after the first fills
the leftmost column that's still only 1 row tall).

Builds tmux's own internal "layout string" format and applies it via a
single `select-layout <string>` call -- this is what makes the whole
rearrangement ATOMIC (one redraw), instead of the old approach of many
separate break-pane/join-pane/select-layout steps each causing a visible
intermediate jump.
"""
import subprocess


def tmux(*args):
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, check=True
    ).stdout


def assign_columns(pane_ids):
    """Returns a list of columns, each a (top, bottom_or_None) pair of
    pane ids, in left-to-right order."""
    columns = []
    incomplete = []
    for i, pid in enumerate(pane_ids, start=1):
        if i == 1 or i % 2 == 0:
            columns.append([pid])
            incomplete.append(len(columns) - 1)
        else:
            idx = incomplete.pop(0)
            columns[idx].append(pid)
    return [(c[0], c[1] if len(c) > 1 else None) for c in columns]


def _checksum(body):
    csum = 0
    for ch in body:
        csum = (csum >> 1) + ((csum & 1) << 15)
        csum = (csum + ord(ch)) & 0xFFFF
    return f"{csum:04x}"


def build_layout_string(width, height, columns, pane_index_of):
    """columns: output of assign_columns(). pane_index_of: dict mapping
    pane_id -> that pane's #{pane_index} (window-local index used in the
    layout string, NOT the global %N id)."""
    n = len(columns)
    if n == 1 and columns[0][1] is None:
        # Single pane, whole window.
        body = f"{width}x{height},0,0,{pane_index_of[columns[0][0]]}"
        return f"{_checksum(body)},{body}"

    avail_w = width - (n - 1)
    base_w, extra = divmod(avail_w, n)
    col_widths = [base_w + 1 if i < extra else base_w for i in range(n)]

    x = 0
    col_strs = []
    for (top, bottom), w in zip(columns, col_widths):
        if bottom is None:
            col_strs.append(f"{w}x{height},{x},0,{pane_index_of[top]}")
        else:
            avail_h = height - 1
            top_h = avail_h // 2
            bot_h = avail_h - top_h
            col_strs.append(
                f"{w}x{height},{x},0["
                f"{w}x{top_h},{x},0,{pane_index_of[top]},"
                f"{w}x{bot_h},{x},{top_h + 1},{pane_index_of[bottom]}"
                f"]"
            )
        x += w + 1

    body = f"{width}x{height},0,0{{{','.join(col_strs)}}}"
    return f"{_checksum(body)},{body}"


def apply_grid_layout(win):
    """Recomputes and atomically applies the grid layout for all of a
    window's current panes. Returns the number of panes."""
    panes = []
    for line in tmux(
        "list-panes", "-t", win, "-F", "#{pane_id} #{pane_index}"
    ).splitlines():
        pid, idx = line.split()
        panes.append((pid, int(idx)))

    n = len(panes)
    if n == 0:
        return 0
    if n == 1:
        return 1

    pane_ids = [pid for pid, _ in panes]
    pane_index_of = dict(panes)

    width = int(tmux("display-message", "-p", "-t", win, "#{window_width}").strip())
    height = int(tmux("display-message", "-p", "-t", win, "#{window_height}").strip())

    columns = assign_columns(pane_ids)
    layout = build_layout_string(width, height, columns, pane_index_of)
    subprocess.run(["tmux", "select-layout", "-t", win, layout], check=True)
    return n
