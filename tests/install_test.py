#!/usr/bin/env python3
import os
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
    env = dict(os.environ, HOME=directory, SHELL="/bin/zsh")
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
    print("Installer passed: backups, CLI/skill links, both config locations, and idempotence.")
