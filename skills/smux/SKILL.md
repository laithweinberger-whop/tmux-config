---
name: smux
description: Control tmux panes and communicate between coding agents. Use for creating agent panes or windows, stopping spawned agents, reading terminal output, labeling panes, and sending cross-pane messages. Provides smux for lifecycle operations and tmux-bridge for messaging.
---

# smux

Use `smux` for pane lifecycle and `tmux-bridge` for cross-pane interaction. They share the same targeting code. Run `smux --help` for command options.

## Agent aliases

Use `cod` for `codex --yolo` and `cla` for `claude --dangerously-skip-permissions`. Run `smux install` when setting up a computer: it saves missing aliases in the user's shell startup file, preserves existing aliases (including custom definitions and aliases loaded from another file), and avoids duplicate additions on repeat installs. Start a new shell to load newly added aliases. `smux pane/window -- cod …` and `-- cla …` resolve aliases through the configured interactive shell.

## Create, stop, and close

**Option + −** moves the selected pane into a shared `minimized` window in the same session, creating it if needed. It preserves the running process and keeps focus in the original window, leaving a fresh terminal if its last pane is moved. Switch windows to revisit minimized panes; the shortcut does nothing inside `minimized`.

```bash
smux pane -- cla 'Implement the assigned task'
smux pane -- cod --no-daemon 'Implement the assigned task'
smux window -- cod --no-daemon 'Implement the assigned task'
```

`pane` splits the caller's window and makes it visible. `window` creates a separate window in the caller's session. Choose `window` when the user explicitly requests a tmux window; otherwise use `pane`. Neither replaces the caller. Commands return JSON with exact pane, window, session, and parent IDs. Keep that pane ID for subsequent operations.

`--cwd PATH` before `--` sets the working directory; it defaults to your current directory. With no command, a terminal shell opens. When a command exits or is interrupted, the pane returns to a shell.

```bash
smux stop %12
smux close %12
```

`stop` terminates the child's current process and opens a fresh shell **in the same pane**. It does not save the process's in-memory state. `close` removes only that child pane. Both require its exact `%N` and reject your own pane or another caller's children. Use these lifecycle operations rather than raw `respawn-pane`, `kill-window`, or `kill-session`.

## Restoring agent conversations

SessionStart hooks record exact Claude/Codex conversation IDs against the owning pane. Snapshots save `cla --resume <ID>` or `cod resume <ID> --no-daemon`; they never select the latest conversation implicitly. For Codex identity capture, trust the installed hook through `/hooks` and use `cod --no-daemon` so the agent process belongs to its pane. An unrecorded conversation uses the session picker on restore instead of guessing. Existing running conversations need a new start/resume with the hook enabled. Snapshots older than seven days are removed while retaining at least five backups.

## Context and targets

The installed `codex` launcher passes the launching pane's `TMUX`, `TMUX_PANE`, and Codex process ID through per-chat `shell_environment_policy.set` overrides. Each chat's commands receive their own pane context even when Codex uses a shared daemon. Existing `cod` aliases that invoke `codex` use this automatically; existing chats need to be resumed through the launcher to acquire it. Absolute-path invocations of the original Codex executable bypass the launcher.

The CLI verifies that either its own process or the per-chat Codex process belongs to the claimed pane. Older shared-daemon chats may still carry unverified IDs and receive an error. Never copy the rejected ID into `--from`. Identify the current chat by matching its title, task context, and attached session in `tmux list-panes -a` and `tmux list-clients`, then pass that verified pane explicitly. If it is ambiguous, ask the user for the target. Do not guess from the working directory or choose whichever client is active.

The CLI never scans servers or guesses an active window. Outside tmux, or for an older chat without propagated context, establish the intended socket and caller explicitly:

```bash
smux --socket /path/to/socket --from %3 pane -- cod --no-daemon 'Task'
```

The same global options work with `tmux-bridge`. A missing or stale context is an error; obtain the intended caller instead of substituting an arbitrary active pane.

After creation, verify the returned session/window match the established parent, the new pane is selected, and the window is unzoomed. A successful launch in a different session does not make the pane visible to the user.

- `%N`: exact pane on this server, including another window.
- Labels and numeric pane indexes: scoped to the caller's window. Ambiguous labels fail.
- `session:window.pane`: full target with numeric window and pane indexes.
- `tmux-bridge list`: caller's window; `list --all`: all windows on this server.

## Messaging

| Command | Purpose |
|---|---|
| `tmux-bridge id` | Validate and print your caller pane ID |
| `tmux-bridge name %3 reviewer` | Label a pane; labels must be unique within its window |
| `tmux-bridge resolve reviewer` | Resolve a local label to an exact pane ID |
| `tmux-bridge read %12 20` | Capture output and satisfy the read guard |
| `tmux-bridge message %12 'Task or result'` | Type text with sender and reply pane IDs; no Enter |
| `tmux-bridge type %12 'text'` | Type literal text; no Enter |
| `tmux-bridge keys %12 Enter` | Send keys after reading the pane |
| `tmux-bridge doctor` | Show the validated socket, caller, window, and zoom state |

The read guard belongs to this caller, server, and target process, expires after five minutes, and is consumed by each input action. Keep the read → type/message → read → Enter sequence:

```bash
tmux-bridge read %12 20
tmux-bridge message %12 'Review src/auth.ts. Send findings when finished, or a blocker if needed.'
tmux-bridge read %12 20
tmux-bridge keys %12 Enter
```

A message includes `[tmux-bridge from:reviewer pane:%3]`; use the exact pane ID for a needed reply. Parent and child should communicate for the assignment, material blockers/questions, and the final result. Do not acknowledge acknowledgements, send routine progress nudges, or ask for status while the child is still working unless the user requests it. Batch related information into one message.

After sending, continue useful work. Do not poll agent panes for replies; the child sends results to the parent's pane. Read an agent pane before interacting and after typing to verify delivery. Read non-agent panes as needed to inspect their output. Receiving a message does not itself require a reply.
