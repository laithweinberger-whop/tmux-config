#!/usr/bin/env python3
import argparse
import os
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

    shell = Path(os.environ.get("SHELL", "/bin/sh")).name
    rc = home / (".zshrc" if shell == "zsh" else ".bashrc" if shell == "bash" else ".profile")
    contents = rc.read_text() if rc.exists() else ""
    if ".smux/bin" not in contents:
        if rc.exists():
            saved = backup / rc.name
            saved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(rc, saved)
        with rc.open("a") as out:
            out.write('\nexport PATH="$HOME/.smux/bin:$PATH"\n')

    if not args.no_reload:
        socket = os.environ.get("TMUX", "").rsplit(",", 2)[0]
        command = ["tmux"] + (["-S", socket] if socket else [])
        if subprocess.run(command + ["has-session"], capture_output=True, check=False).returncode == 0:
            subprocess.run(command + ["source-file", str(home / ".tmux.conf")], check=True)
    print("Installed tmux, smux, tmux-bridge, and the shared smux skill.")
    if backup.exists():
        print(f"Backups: {backup}")
    print('For this shell: export PATH="$HOME/.smux/bin:$PATH"')
    print("Start a new agent conversation to load the updated skill.")
    print("Other skill-capable agents: npx skills add " + shlex.quote(str(repo / "skills/smux")) + " -g --all")


if __name__ == "__main__":
    main()
