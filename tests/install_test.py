#!/usr/bin/env python3
import os
import json
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


with tempfile.TemporaryDirectory(prefix="smux-install-") as directory:
    home = Path(directory)
    (home / ".tmux.conf").write_text("original tmux config\n")
    (home / ".smux/bin").mkdir(parents=True)
    (home / ".smux/bin/smux").write_text("original installer\n")
    (home / ".agents/skills/smux").mkdir(parents=True)
    (home / ".agents/skills/smux/SKILL.md").write_text("original skill\n")
    (home / ".codex/skills").mkdir(parents=True)
    (home / ".codex/skills/smux").symlink_to("../../.agents/skills/smux")
    (home / ".config/tmux").mkdir(parents=True)
    (home / ".config/tmux/tmux.conf").symlink_to(home / ".smux/tmux.conf")
    (home / ".zshrc").write_text("original shell settings\n")
    env = dict(os.environ, HOME=directory, ZDOTDIR=directory, CODEX_HOME=str(home / ".codex"), CLAUDE_CONFIG_DIR=str(home / ".claude"), SHELL="/bin/zsh")
    for agent, file in (("claude", "settings.json"), ("codex", "hooks.json")):
        config = home / ("." + agent) / file
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}))
    for _ in range(2):
        subprocess.run([str(REPO / "install.sh"), "--no-reload"], env=env, check=True)
    backups = list((home / ".tmux/backups").iterdir())
    assert len(backups) == 1
    assert (backups[0] / ".tmux.conf").read_text() == "original tmux config\n"
    assert (backups[0] / ".smux/bin/smux").read_text() == "original installer\n"
    assert (backups[0] / ".agents/skills/smux/SKILL.md").read_text() == "original skill\n"
    assert (backups[0] / ".zshrc").read_text() == "original shell settings\n"
    for directory in (".agents", ".codex", ".claude", ".cursor", ".gemini", ".copilot", ".config/opencode", ".config/agents"):
        assert (home / directory / "skills/smux").resolve() == REPO / "skills/smux"
    assert (home / ".tmux.conf").resolve() == (home / ".config/tmux/tmux.conf").resolve() == REPO / "tmux.conf"
    assert (home / ".zshrc").read_text().count(".smux/bin") == 1
    for binary in ("smux", "tmux-bridge"):
        assert "3.0.0" in subprocess.check_output([str(home / ".smux/bin" / binary), "version"], env=env, text=True)
    assert (home / ".tmux/scripts/reflow-grid.sh").resolve() == REPO / "scripts/reflow-grid.sh"
    for agent, file in (("claude", "settings.json"), ("codex", "hooks.json")):
        groups = json.loads((home / ("." + agent) / file).read_text())["hooks"]["SessionStart"]
        assert len(groups) == 2
        assert groups[0]["hooks"][0]["command"] == "echo existing"
        assert groups[1]["hooks"][0]["command"].endswith("register " + agent)
    aliases = subprocess.check_output(["/bin/zsh", "-ic", "alias cod; alias cla"], env=env, text=True)
    assert "cod='codex --yolo'" in aliases
    assert "cla='claude --dangerously-skip-permissions'" in aliases
    print("Installer passed: backups, CLI/skill links, both config locations, and idempotence.")

for shell in ("/bin/zsh", "/bin/bash", "/bin/sh"):
    with tempfile.TemporaryDirectory(prefix="smux-alias-install-") as directory:
        home = Path(directory)
        rc = home / (".zshrc" if shell.endswith("zsh") else ".bashrc" if shell.endswith("bash") else ".profile")
        (home / "aliases").write_text("alias cod='codex --model custom'\n")
        original = '. "$HOME/aliases"\nalias other=kept\n'
        rc.write_text(original)
        env = dict(os.environ, HOME=directory, ZDOTDIR=directory, CODEX_HOME=str(home / ".codex"), CLAUDE_CONFIG_DIR=str(home / ".claude"), SHELL=shell)
        for _ in range(2):
            subprocess.run([str(REPO / "install.sh"), "--no-reload"], env=env, check=True, stdout=subprocess.DEVNULL)
        assert rc.read_text().startswith(original)
        assert "alias cod" not in rc.read_text()
        assert rc.read_text().count("alias cla=") == 1
        command = "alias cod; alias cla; alias other"
        if shell == "/bin/sh":
            command = '. "$HOME/.profile"; ' + command
        aliases = subprocess.check_output([shell, "-ic", command], env=env, text=True)
        assert "codex --model custom" in aliases
        assert "claude --dangerously-skip-permissions" in aliases
        assert "other" in aliases and "kept" in aliases
        rc.write_text(original + "alias cla='claude --model custom'\n")
        subprocess.run([str(REPO / "install.sh"), "--no-reload"], env=env, check=True, stdout=subprocess.DEVNULL)
        assert rc.read_text().count("alias cla=") == 1
        assert "alias cod" not in rc.read_text()

with tempfile.TemporaryDirectory(prefix="smux-brew-install-") as directory:
    home = Path(directory)
    brew = home / "brew"
    brew.write_text("#!/bin/sh\nprintf 'export BREW_CACHE_TEST=loaded\\n'\n")
    brew.chmod(0o755)
    rc = home / ".zshrc"
    original = 'eval "$(' + str(brew) + ' shellenv)"\nalias cod="custom cod"\nalias cla="custom cla"\n'
    rc.write_text(original)
    env = dict(os.environ, HOME=directory, ZDOTDIR=directory, CODEX_HOME=str(home / ".codex"), CLAUDE_CONFIG_DIR=str(home / ".claude"), SHELL="/bin/zsh")
    subprocess.run([str(REPO / "install.sh"), "--no-reload"], env=env, check=True, stdout=subprocess.DEVNULL)
    brew.unlink()
    value = subprocess.check_output(["/bin/zsh", "-ic", 'printf "%s" "$BREW_CACHE_TEST"'], env=env, text=True)
    assert value == "loaded"
    assert 'alias cod="custom cod"\nalias cla="custom cla"' in rc.read_text()
    subprocess.run([str(REPO / "install.sh"), "--no-reload"], env=env, check=True, stdout=subprocess.DEVNULL)
    assert len(list((home / ".tmux/backups").iterdir())) == 1
print("Alias preservation, sourced aliases, repeat installs, and cached Homebrew startup passed.")
