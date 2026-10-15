#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Install tmux configuration, smux, and agent skills")
    parser.add_argument("--no-reload", action="store_true")
    args = parser.parse_args()
    for command in ("tmux", "bash"):
        if not shutil.which(command):
            parser.error(f"install {command} first")
    repo = Path(__file__).resolve().parents[1]
    home = Path.home()
    backup = home / ".tmux/backups" / datetime.now().strftime("smux-%Y%m%d-%H%M%S-%f")

    def link(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        if target.exists() or target.is_symlink():
            saved = backup / target.relative_to(home)
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(saved))
        target.symlink_to(source)

    link(repo / "tmux.conf", home / ".tmux.conf")
    link(repo / "tmux.conf", home / ".config/tmux/tmux.conf")
    link(repo / "smux/tmux.conf", home / ".smux/tmux.conf")
    for script in (repo / "scripts").iterdir():
        if script.suffix in (".sh", ".py") and script.name != "install.py":
            link(script, home / ".tmux/scripts" / script.name)
    for name in ("smux", "tmux-bridge", "smux-run"):
        link(repo / "smux/bin" / name, home / ".smux/bin" / name)
    link(repo / "skills/smux", home / ".agents/skills/smux")
    for directory in (".codex", ".claude", ".cursor", ".gemini", ".copilot", ".config/opencode", ".config/agents"):
        link(repo / "skills/smux", home / directory / "skills/smux")

    shell_path = os.environ.get("SHELL", "/bin/sh")
    shell = Path(shell_path).name
    rc_directory = Path(os.environ.get("ZDOTDIR", str(home))) if shell == "zsh" else home
    rc = rc_directory / (".zshrc" if shell == "zsh" else ".bashrc" if shell == "bash" else ".profile")
    contents = rc.read_text() if rc.exists() else ""
    updated = contents
    if shell == "zsh":
        brew_line = re.search(r'^eval "\$\((/[^ \n]+/brew) shellenv\)"$', contents, re.MULTILINE)
        if brew_line:
            brew_env = subprocess.check_output([brew_line[1], "shellenv", "zsh"], text=True)
            cache = home / ".smux/homebrew.zsh"
            cache.write_text(brew_env)
            updated = updated.replace(brew_line[0], 'source "$HOME/.smux/homebrew.zsh"', 1)
    additions = []
    if ".smux/bin" not in contents:
        additions.append('export PATH="$HOME/.smux/bin:$PATH"')
    if shell in ("zsh", "bash", "sh"):
        probe = 'for name in cod cla; do alias "$name" >/dev/null 2>&1 && printf "smux-alias:%s\\n" "$name"; done; :'
        if shell == "sh":
            probe = '. ' + shlex.quote(str(rc)) + '; ' + probe if rc.exists() else probe
        result = subprocess.run([shell_path, "-ic", probe], capture_output=True, text=True, timeout=30, check=True)
        present = set(result.stdout.splitlines())
        for name, command in (("cod", "codex --yolo"), ("cla", "claude --dangerously-skip-permissions")):
            if "smux-alias:" + name not in present:
                additions.append(f"alias {name} >/dev/null 2>&1 || alias {name}={shlex.quote(command)}")
    else:
        print(f"Alias setup skipped for unsupported shell: {shell}")
    if additions:
        updated += "\n" + "\n".join(additions) + "\n"
    if updated != contents:
        if rc.exists():
            saved = backup / rc.name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rc, saved)
        rc.parent.mkdir(parents=True, exist_ok=True)
        rc.write_text(updated)

    for agent, config in (
        ("claude", Path(os.environ.get("CLAUDE_CONFIG_DIR", str(home / ".claude"))) / "settings.json"),
        ("codex", Path(os.environ.get("CODEX_HOME", str(home / ".codex"))) / "hooks.json"),
    ):
        settings = json.loads(config.read_text()) if config.exists() else {}
        command = 'python3 "$HOME/.tmux/scripts/agent-sessions.py" register ' + agent
        groups = settings.setdefault("hooks", {}).setdefault("SessionStart", [])
        if not any(hook.get("command") == command for group in groups for hook in group.get("hooks", [])):
            if config.exists():
                saved = backup / agent / config.name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(config, saved)
            groups.append({"hooks": [{"type": "command", "command": command}]})
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(json.dumps(settings, indent=2) + "\n")

    if not args.no_reload:
        socket = os.environ.get("TMUX", "").rsplit(",", 2)[0]
        command = ["tmux"] + (["-S", socket] if socket else [])
        if subprocess.run(command + ["has-session"], capture_output=True, check=False).returncode == 0:
            subprocess.run(command + ["source-file", str(home / ".tmux.conf")], check=True)
    print("Installed tmux, smux, tmux-bridge, and the shared smux skill.")
    if backup.exists():
        print(f"Backups: {backup}")
    print('For this shell: export PATH="$HOME/.smux/bin:$PATH"')
    print("For exact Codex restoration, review the session-recording hook in /hooks and launch with --no-daemon.")
    print("Start a new agent conversation to load the updated skill.")
    print("Other skill-capable agents: npx skills add " + shlex.quote(str(repo / "skills/smux")) + " -g --all")


if __name__ == "__main__":
    main()
