#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path


def tmux(socket, *args):
    return subprocess.check_output(["tmux", "-S", socket, *args], text=True).strip()


def processes():
    output = subprocess.check_output(["ps", "-axo", "pid=,ppid=,lstart=,args="], text=True)
    result = {}
    for line in output.splitlines():
        fields = line.split(None, 7)
        if len(fields) == 8:
            command = fields[7].split()
            if not command:
                continue
            name = Path(command[0]).name
            if name == "codex" and command[1:2] == ["app-server"]:
                name = "codex-app-server"
            result[int(fields[0])] = (int(fields[1]), " ".join(fields[2:7]), name)
    return result


def owner(processes_by_pid, panes_by_pid, pid, agent):
    agent_pid = None
    visited = set()
    while pid in processes_by_pid and pid not in visited:
        visited.add(pid)
        parent, started, command = processes_by_pid[pid]
        is_claude = command == "claude" or re.fullmatch(r"\d+\.\d+\.\d+", command)
        if command == "codex" or is_claude:
            if agent_pid is not None or (agent == "codex") != (command == "codex"):
                return None
            agent_pid = pid
        if pid in panes_by_pid:
            if agent_pid is not None:
                return panes_by_pid[pid], agent_pid, processes_by_pid[agent_pid][1]
            return None
        pid = parent
    return None


def register(agent):
    payload = json.load(sys.stdin)
    session_id = payload.get("session_id", "")
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", session_id):
        raise ValueError("invalid agent session ID")
    context = os.environ.get("TMUX", "").rsplit(",", 2)
    if len(context) != 3:
        return
    socket = context[0]
    panes = tmux(socket, "list-panes", "-a", "-F", "#{pane_pid} #{pane_id}")
    panes_by_pid = {int(pid): pane for pid, pane in (line.split() for line in panes.splitlines())}
    current = processes()
    match = owner(current, panes_by_pid, os.getpid(), agent)
    if match is None:
        print("smux: session ID was not recorded because its process is not owned by a tmux pane (for Codex, use --no-daemon).", file=sys.stderr)
        return
    pane, pid, started = match
    value = json.dumps({"agent": agent, "session_id": session_id, "pid": pid, "started": started})
    tmux(socket, "set-option", "-p", "-t", pane, "@smux_agent_session", value)


def rewrite_snapshot(contents, records, current):
    output = []
    for line in contents.splitlines(keepends=True):
        fields = line.rstrip("\n").split("\t")
        if len(fields) == 11 and fields[0] == "pane":
            record = records.get((fields[1], fields[2], fields[5]))
            if record and record.get("agent") in ("codex", "claude"):
                process = current.get(record.get("pid"))
                session_id = record.get("session_id", "")
                if process and process[1] == record.get("started") and re.fullmatch(r"[a-zA-Z0-9_-]+", session_id):
                    command = ["cod", "resume", session_id, "--no-daemon"] if record["agent"] == "codex" else ["cla", "--resume", session_id]
                    fields[9] = record["agent"]
                    fields[10] = ":" + shlex.join(command)
                    line = "\t".join(fields) + "\n"
        output.append(line)
    return "".join(output)


def save(path):
    socket = os.environ.get("TMUX", "").rsplit(",", 2)[0]
    rows = tmux(socket, "list-panes", "-a", "-F", "#{session_name}\t#{window_index}\t#{pane_index}\t#{@smux_agent_session}")
    records = {}
    for line in rows.splitlines():
        fields = line.split("\t", 3)
        if len(fields) == 4 and fields[3]:
            records[tuple(fields[:3])] = json.loads(fields[3])
    snapshot = Path(path)
    contents = snapshot.read_text()
    updated = rewrite_snapshot(contents, records, processes())
    if updated != contents:
        snapshot.write_text(updated)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    start = sub.add_parser("register")
    start.add_argument("agent", choices=("codex", "claude"))
    snapshot = sub.add_parser("save")
    snapshot.add_argument("path")
    args = parser.parse_args()
    if args.action == "register":
        register(args.agent)
    else:
        save(args.path)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"smux: could not record agent session: {error}", file=sys.stderr)
        sys.exit(1)
