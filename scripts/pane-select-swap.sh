#!/usr/bin/env bash
# Shift+click accumulates up to 2 panes to swap (tracked via global
# options since tmux's own pane mark only tracks one at a time).
# Selected panes are highlighted yellow via a per-pane @swap_selected
# option that pane-border-style reads live -- tmux's native mark only
# supports highlighting one pane, so this is tracked separately to show
# both. Clicking an already-selected pane deselects it; clicking a third
# pane starts a fresh selection.
PANE="$1"
SEL1="$(tmux show-options -gqv @swap_sel_1)"
SEL2="$(tmux show-options -gqv @swap_sel_2)"

if [ -n "$SEL1" ] && [ "$PANE" = "$SEL1" ]; then
	tmux set-option -gu @swap_sel_1
	tmux set-option -pu -t "$PANE" @swap_selected
elif [ -n "$SEL2" ] && [ "$PANE" = "$SEL2" ]; then
	tmux set-option -gu @swap_sel_2
	tmux set-option -pu -t "$PANE" @swap_selected
elif [ -z "$SEL1" ]; then
	tmux set-option -g @swap_sel_1 "$PANE"
	tmux set-option -p -t "$PANE" @swap_selected 1
elif [ -z "$SEL2" ]; then
	tmux set-option -g @swap_sel_2 "$PANE"
	tmux set-option -p -t "$PANE" @swap_selected 1
else
	tmux set-option -pu -t "$SEL1" @swap_selected
	tmux set-option -pu -t "$SEL2" @swap_selected
	tmux set-option -gu @swap_sel_2
	tmux set-option -g @swap_sel_1 "$PANE"
	tmux set-option -p -t "$PANE" @swap_selected 1
fi

# Without this, tmux doesn't repaint the border until its next natural
# redraw trigger, so the highlight can lag well behind the actual click.
tmux refresh-client
