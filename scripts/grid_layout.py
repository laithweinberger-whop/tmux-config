import subprocess


def tmux(*args):
    return subprocess.run(
        ["tmux", *args], capture_output=True, text=True, check=True
    ).stdout


def assign_columns(pane_ids):
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


def build_layout_string(width, height, columns, pane_number_of):
    n = len(columns)
    if n == 1 and columns[0][1] is None:
        # Single pane, whole window.
        body = f"{width}x{height},0,0,{pane_number_of[columns[0][0]]}"
        return f"{_checksum(body)},{body}"

    avail_w = width - (n - 1)
    base_w, extra = divmod(avail_w, n)
    col_widths = [base_w + 1 if i < extra else base_w for i in range(n)]

    x = 0
    col_strs = []
    for (top, bottom), w in zip(columns, col_widths):
        if bottom is None:
            col_strs.append(f"{w}x{height},{x},0,{pane_number_of[top]}")
        else:
            avail_h = height - 1
            top_h = avail_h // 2
            bot_h = avail_h - top_h
            col_strs.append(
                f"{w}x{height},{x},0["
                f"{w}x{top_h},{x},0,{pane_number_of[top]},"
                f"{w}x{bot_h},{x},{top_h + 1},{pane_number_of[bottom]}"
                f"]"
            )
        x += w + 1

    body = f"{width}x{height},0,0{{{','.join(col_strs)}}}"
    return f"{_checksum(body)},{body}"


def cache_layouts(windows, reflow=None):
    commands = []
    dimensions = {}
    for _, width, height, count in windows:
        size = (int(width), int(height))
        dimensions[size] = max(dimensions.get(size, 0), int(count) + 1, 32)
    # tmux assigns existing panes in order; cached pane numbers are placeholders.
    for (width, height), count in dimensions.items():
        for n in range(1, count + 1):
            pane_ids = list(range(n))
            layout = build_layout_string(
                width, height, assign_columns(pane_ids), {pid: pid for pid in pane_ids}
            )
            commands.append(
                f"set-option -g @grid_layout_{width}x{height}_{n} '{layout}'"
            )
    if reflow is not None:
        commands.append(
            f"run-shell -C -t {reflow} 'if-shell -F \"#{{==:#{{window_id}},{reflow}}}\" "
            "{ #{E:@grid_reflow} }'"
        )
    if commands:
        subprocess.run(
            ["tmux", "source-file", "-"], input="\n".join(commands),
            capture_output=True, text=True, check=True,
        )


def cache_all_layouts():
    windows = [line.split() for line in tmux(
        "list-windows", "-a", "-F",
        "#{window_id} #{window_width} #{window_height} #{window_panes}",
    ).splitlines()]
    cache_layouts(windows)


def apply_grid_layout(win, *size):
    if size:
        window = (win, *size)
    else:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", win, "-F",
             "#{window_id} #{window_width} #{window_height} #{window_panes}"],
            capture_output=True, text=True,
        )
        if result.returncode or not result.stdout.strip():
            return
        window = result.stdout.split()
        if len(window) != 4 or window[0] != win:
            return
    cache_layouts([window], reflow=win)
