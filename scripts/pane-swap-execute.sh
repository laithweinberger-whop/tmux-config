#!/usr/bin/env bash
# Swaps the two shift-click-selected panes (a single atomic swap-pane
# call, so it's instant -- no layout recompute needed since swapping
# doesn't change positions/sizes, just which pane occupies which slot).
# The resulting arrangement is picked up by the normal ~30s autosave like
# any other layout change, so it's what gets restored next time too.
SEL1="$(tmux show-options -gqv @swap_sel_1)"
SEL2="$(tmux show-options -gqv @swap_sel_2)"

if [ -n "$SEL1" ] && [ -n "$SEL2" ]; then
	tmux swap-pane -s "$SEL1" -t "$SEL2"
fi

[ -n "$SEL1" ] && tmux set-option -pu -t "$SEL1" @swap_selected
[ -n "$SEL2" ] && tmux set-option -pu -t "$SEL2" @swap_selected
tmux set-option -gu @swap_sel_1
tmux set-option -gu @swap_sel_2
tmux refresh-client
