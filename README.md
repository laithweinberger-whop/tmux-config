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

## Update

```sh
git pull --ff-only
./install.sh
```

`smux install` and `smux update` reapply this local checkout. They no longer download upstream defaults over the custom configuration. Pull the repository first to get newer code.

## Agent panes

```sh
smux pane -- codex 'Implement the assigned task'
smux window -- claude 'Implement the assigned task'
smux stop %12
smux close %12
```

Creation returns JSON containing the exact pane ID. `pane` opens in the caller's window; `window` explicitly creates a new window in the same session. Both bring the new pane into view in that session. Commands return to a shell on normal exit or Ctrl-C. `stop` terminates the child process and replaces it with a fresh shell in the same pane; `close` removes only that pane. Neither accepts the caller's own pane or children owned by another caller.

The caller is determined by `TMUX` and `TMUX_PANE`, not the currently selected window. Outside tmux use `smux --socket PATH --from %N …`. Labels and numeric indexes are local to that caller's window; use an exact `%N` to address another window. Missing context or ambiguous targets fail without guessing.

Messaging retains the read → message → read → Enter workflow. Read permissions are scoped to caller, server, and target process. Agent guidance calls for assignments, blockers/questions, and results, without routine status nudges or acknowledgement loops. See [the skill](skills/smux/SKILL.md).

## Verify

```sh
python3 tests/smux_test.py --rounds 20
python3 tests/install_test.py
python3 tests/benchmark.py --help
```

Tests use private tmux sockets and temporary homes. Timing results and earlier grid benchmarks are in [BENCHMARKS.md](BENCHMARKS.md). The smux base configuration and skill originated from [ShawnPana/smux](https://github.com/ShawnPana/smux); its license is retained in [smux/LICENSE](smux/LICENSE).
