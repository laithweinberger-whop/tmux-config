#!/usr/bin/env python3
import json
import os
import queue
import shlex
import subprocess
import tempfile
import threading
import sys
import time
from pathlib import Path
from smux_test import Server, REPO, CLI


with tempfile.TemporaryDirectory(prefix="smux-codex-launcher-") as directory:
    root = Path(directory)
    server = Server(root, "tmux")
    fake_bin = root / "bin"
    fake_bin.mkdir()
    fake = fake_bin / "codex"
    fake.write_text("#!/usr/bin/python3\nimport json,os,sys,time\nwith open(os.environ['CAPTURE'], 'w') as file:\n json.dump({'argv':sys.argv[1:], 'pid':os.getpid()},file)\ntime.sleep(30)\n")
    fake.chmod(0o755)
    launcher = REPO / "smux/bin/codex"
    launches = []
    try:
        for index in (1, 2):
            capture = root / f"{index}.json"
            command = shlex.join(["/usr/bin/env", "PATH=" + str(launcher.parent) + ":" + str(fake_bin) + ":" + os.environ["PATH"],
                                  "CAPTURE=" + str(capture), str(launcher), "resume", f"chat-{index}"])
            pane = server.tmux("new-window", "-t", "main:", "-P", "-F", "#{pane_id}", command)
            deadline = time.monotonic() + 5
            while (not capture.exists() or not capture.read_text()) and time.monotonic() < deadline:
                time.sleep(.02)
            assert capture.exists(), server.tmux("capture-pane", "-p", "-t", pane)
            launch = json.loads(capture.read_text())
            argv = launch["argv"]
            assert argv[-2:] == ["resume", f"chat-{index}"], argv
            values = {}
            for option, setting in zip(argv[:-2:2], argv[1:-2:2]):
                assert option == "-c"
                key, value = setting.split("=", 1)
                values[key.removeprefix("shell_environment_policy.set.")] = json.loads(value)
            assert values["TMUX_PANE"] == pane
            assert values["SMUX_CODEX_PID"] == str(launch["pid"])
            launches.append((pane, values))
        for pane, values in launches[::-1] + launches:
            env = dict(server.env, **values)
            result = subprocess.run([str(CLI), "doctor"], env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stderr
            assert json.loads(result.stdout)["caller"] == pane
        stale = dict(server.env, **launches[0][1])
        stale["TMUX_PANE"] = launches[1][0]
        result = subprocess.run([str(CLI), "pane"], env=stale, capture_output=True, text=True)
        assert result.returncode != 0 and "does not own" in result.stderr
        if len(sys.argv) == 2:
            (root / "codex-home").mkdir()
            process = subprocess.Popen([sys.argv[1], "app-server", "--stdio"], env=dict(server.env, CODEX_HOME=str(root / "codex-home")),
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None, text=True)
            messages = queue.Queue()
            threading.Thread(target=lambda: [messages.put(json.loads(line)) for line in process.stdout], daemon=True).start()
            requests = iter(range(100))
            def rpc(method, params):
                request = next(requests)
                process.stdin.write(json.dumps({"id": request, "method": method, "params": params}) + "\n")
                process.stdin.flush()
                while True:
                    response = messages.get(timeout=15)
                    if response.get("id") == request:
                        assert "error" not in response, response
                        return response["result"]
            try:
                rpc("initialize", {"clientInfo": {"name": "smux-test", "version": "1"}, "capabilities": {"experimentalApi": True}})
                threads = []
                for pane, values in launches:
                    thread = rpc("thread/start", {"cwd": str(root), "ephemeral": True,
                                                 "config": {"shell_environment_policy.set": values}})["thread"]["id"]
                    threads.append((pane, thread))
                for index, (pane, thread) in enumerate(threads[::-1] + threads):
                    output = root / f"doctor-{index}.json"
                    rpc("thread/shellCommand", {"threadId": thread, "command": shlex.join([str(CLI), "doctor"]) + " > " + shlex.quote(str(output)), "timeoutMs": 5000})
                    deadline = time.monotonic() + 10
                    while (not output.exists() or not output.read_text()) and time.monotonic() < deadline:
                        time.sleep(.02)
                    assert json.loads(output.read_text())["caller"] == pane
                print("Installed Codex app-server delivered correct origins for interleaved commands from two threads.")
            finally:
                process.terminate()
                process.wait(timeout=5)
        print("Two launchers passed distinct per-chat pane IDs; interleaved daemon commands kept their correct origins.")
    finally:
        server.tmux("kill-server")
