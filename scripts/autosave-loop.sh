#!/usr/bin/env bash
# Runs for the lifetime of the tmux server, saving the full session
# (layout, pane working dirs, running programs) every 30s so it can be
# restored after a reboot/crash. Guarded by a lockfile so re-sourcing
# tmux.conf doesn't spawn duplicate loops.

LOCKFILE="$HOME/.tmux/autosave.lock"
SAVE_SCRIPT="$HOME/.tmux/plugins/tmux-resurrect/scripts/save.sh"

if [ -f "$LOCKFILE" ] && kill -0 "$(cat "$LOCKFILE" 2>/dev/null)" 2>/dev/null; then
	exit 0
fi
echo $$ > "$LOCKFILE"
trap 'rm -f "$LOCKFILE"' EXIT

while true; do
	sleep 30
	"$SAVE_SCRIPT" "quiet" >/dev/null 2>&1
done
