# tmux + smux

Personal tmux configuration with fast grid layouts, explicit agent pane targeting, and a shared smux skill.

## Install

Requires tmux, Python 3.9+, and Bash. Tested on macOS with tmux 3.7c.

```sh
git clone https://github.com/laithweinberger-whop/tmux-config.git
cd tmux-config
./install.sh
export PATH="$HOME/.smux/bin:$PATH"
```

The installer links both tmux config locations to this checkout, installs `smux` and `tmux-bridge`, and installs the skill for Codex, Claude Code, Cursor, Gemini CLI, GitHub Copilot, OpenCode, and agents using the shared `.agents` directory. Existing files are moved to a timestamped directory under `~/.tmux/backups/`. Repeat installation is safe; keep this checkout in place because the installation uses symlinks.

The installer saves missing `cod` (`codex --yolo`) and `cla` (`claude --dangerously-skip-permissions`) aliases for zsh, Bash, or sh, preserving existing definitions. For zsh configurations with an absolute `brew shellenv` startup line, it saves that generated setup in `~/.smux/homebrew.zsh` so new shells source it without launching Homebrew. The original shell file is backed up.

Start a new agent conversation to load the updated skill. For all other agents supported by the [Skills CLI](https://github.com/vercel-labs/skills#supported-agents), install this repository's skill with:

```sh
npx skills add ./skills/smux -g --all
```

`./install.sh --no-reload` installs without reloading a running tmux server. Installation never restarts the server or kills existing panes. The smux base config is sourced first, then the custom grid/key bindings, so it cannot overwrite them on update.

For session persistence on a new machine, install TPM and the plugins declared in `tmux.conf`:

```sh
git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
~/.tmux/plugins/tpm/bin/install_plugins
```

Skip the clone if TPM is already installed.

## Saved agent sessions

Snapshots retain window layouts, working directories, scrollback, and recorded agent identities. The installer adds a SessionStart hook to Claude Code and Codex without replacing existing hooks. The hook maps the agent process to its owning pane and records the exact session ID; the next snapshot saves `cod resume <ID> --no-daemon` or `cla --resume <ID>` in that pane's command field. Snapshot cleanup retains the newest five files and removes older files after seven days.

Codex requires reviewing and trusting the new hook in `/hooks`. Use `cod --no-daemon` for automatic identity capture: a shared daemon is not owned by an individual pane, so the recorder refuses to guess its owner. Existing conversations must restart or resume with the hook enabled before their IDs can be recorded. A pane without a recorded ID opens the agent's session picker when its process is recognized; it never automatically chooses the latest chat. Only Claude Code and Codex have identity capture configured.

## Update

```sh
git pull --ff-only
./install.sh
```

`smux install` and `smux update` reapply this local checkout. They no longer download upstream defaults over the custom configuration. Pull the repository first to get newer code.

## Agent panes

Press **Option + −** to move the selected pane into the same session's **minimized** window. The window is created on first use and reused thereafter. The pane's running process stays alive, and focus stays in the original window. Minimizing its last pane leaves a fresh terminal behind. Use **Option + U/H** or **Ctrl+B, W** to visit the minimized window. Pressing the shortcut inside that window does nothing.

```sh
smux pane -- cod --no-daemon 'Implement the assigned task'
smux window -- cla 'Implement the assigned task'
smux stop %12
smux close %12
```

Creation returns JSON containing the exact pane ID. `pane` opens in the caller's window; `window` explicitly creates a new window in the same session. Both bring the new pane into view in that session. Commands return to a shell on normal exit or Ctrl-C. `stop` terminates the child process and replaces it with a fresh shell in the same pane; `close` removes only that pane. Neither accepts the caller's own pane or children owned by another caller.

The installer adds a `codex` launcher to `~/.smux/bin`. It forwards to the original Codex executable and passes the launching pane's `TMUX`, `TMUX_PANE`, and Codex process ID as per-chat command-environment overrides. Shared-daemon chats therefore receive their own pane context. Existing aliases are preserved; `cod='codex --yolo'` automatically uses the launcher through PATH. Already-running chats need to be resumed through the launcher to acquire these settings. Absolute-path Codex invocations and remote app-server connections bypass this integration.

The caller is determined by `TMUX` and `TMUX_PANE`, with process ancestry verifying either the command itself or its per-chat Codex process. Unverified context fails before creating anything. For older chats with stale context, identify the actual chat's pane, then use `smux --socket PATH --from %N …`. The explicit target is also required outside tmux. Labels and numeric indexes are local to that caller's window; use an exact `%N` to address another window. Missing context or ambiguous targets fail without guessing.

Messaging retains the read → message → read → Enter workflow. Read permissions are scoped to caller, server, and target process. Agent guidance calls for assignments, blockers/questions, and results, without routine status nudges or acknowledgement loops. See [the skill](skills/smux/SKILL.md).

## Verify

```sh
python3 tests/smux_test.py --rounds 20
python3 tests/install_test.py
python3 tests/agent_sessions_test.py
python3 tests/minimize_pane_test.py
python3 tests/codex_launcher_test.py
python3 tests/codex_launcher_test.py /absolute/path/to/original/codex
python3 tests/benchmark.py --help
```

Tests use private tmux sockets and temporary homes. Timing results and earlier grid benchmarks are in [BENCHMARKS.md](BENCHMARKS.md). The smux base configuration and skill originated from [ShawnPana/smux](https://github.com/ShawnPana/smux); its license is retained in [smux/LICENSE](smux/LICENSE).
