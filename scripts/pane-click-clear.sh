#!/usr/bin/env bash
# Runs on every plain (non-shift) click, clearing any pending swap
# selection -- clicking away is expected to cancel it, like dismissing a
# selection in most UIs. No-op if nothing is selected.
SEL1="$(tmux show-options -gqv @swap_sel_1)"
SEL2="$(tmux show-options -gqv @swap_sel_2)"

if [ -n "$SEL1" ] || [ -n "$SEL2" ]; then
	[ -n "$SEL1" ] && tmux set-option -pu -t "$SEL1" @swap_selected
	[ -n "$SEL2" ] && tmux set-option -pu -t "$SEL2" @swap_selected
	tmux set-option -gu @swap_sel_1
	tmux set-option -gu @swap_sel_2
	tmux refresh-client
fi
