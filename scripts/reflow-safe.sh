#!/usr/bin/env bash
# Wrapper for hook-triggered reflows. Deliberately does NOT try to identify
# "the one window a kill/exit hook fired for" -- tmux's format expansion
# for run-shell (even via a native set-option -F precapture) resolves to
# the wrong window once the triggering pane is already gone, which is
# exactly the case for after-kill-pane/pane-exited. Instead, just reflow
# every window with more than one pane; reflow-grid.sh is idempotent and
# cheap, so this is reliable regardless of which window/session fired.
#
# A single pane close fires BOTH after-kill-pane and pane-exited at once,
# so two of these can start concurrently for the same event. mkdir is
# atomic, so it's used as a lock to make sure only one reflow pass runs at
# a time -- concurrent unsynchronized reflows on the same window (two
# scripts independently breaking/joining panes) can corrupt the layout or
# even destroy a pane. A second, overlapping invocation just skips: the
# first one already ends up observing the same final pane state.
LOCKDIR="$HOME/.tmux/reflow.lock"

if [ -d "$LOCKDIR" ]; then
	# Stale-lock safety net: a crashed run could leave this behind forever.
	lock_age=$(( $(date +%s) - $(stat -f %m "$LOCKDIR" 2>/dev/null || echo 0) ))
	if [ "$lock_age" -lt 10 ]; then
		exit 0
	fi
	rmdir "$LOCKDIR" 2>/dev/null
fi

if ! mkdir "$LOCKDIR" 2>/dev/null; then
	exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

tmux list-windows -a -F '#{window_id} #{window_panes}' 2>/dev/null |
while read -r win npanes; do
	if [ "${npanes:-0}" -gt 1 ]; then
		~/.tmux/scripts/reflow-grid.sh "$win" >/dev/null 2>&1
	fi
done
