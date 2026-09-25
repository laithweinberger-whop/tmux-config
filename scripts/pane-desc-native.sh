#!/usr/bin/env bash
# Native macOS dialog for viewing/editing a pane's description. Pre-fills
# with the existing description (empty if none), so the same action
# covers both writing a new one and reading/editing the existing one.
PANE="$1"
EXISTING="$(tmux show-options -p -t "$PANE" -qv @pane_desc)"

RESULT="$(osascript "$HOME/.tmux/scripts/pane-desc-dialog.applescript" "$EXISTING" 2>/dev/null)"
STATUS=$?

# osascript exits non-zero when the user clicks Cancel (AppleScript
# throws "User canceled" / error -128) -- only save on a real Save click.
if [ $STATUS -eq 0 ]; then
	tmux set-option -p -t "$PANE" @pane_desc "$RESULT"
fi
