#!/usr/bin/env python3
"""Free discriminator for the --profile loading failure (smoke attempt 2).
Every variant aborts pre-API: config-parse errors are local, and the scratch
CODEX_HOME carries no auth material, so nothing can spend.
"""

import os
import subprocess
import tempfile

BAD_TOML = "this is not toml [[[\n"
GOOD_TOML = (
    "[permissions.exec_loop_wall]\n"
    'extends = ":workspace"\n'
    "[permissions.exec_loop_wall.filesystem]\n"
    '"/tmp/probe-sealed" = "deny"\n'
    "[permissions.exec_loop_wall.network]\n"
    "enabled = true\n"
)


def run(label, home_files, argv_extra):
    home = tempfile.mkdtemp(prefix="codex-probe-home.")
    ws = tempfile.mkdtemp(prefix="codex-probe-ws.")
    for name, content in home_files.items():
        path = os.path.join(home, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
    argv = ["codex", "exec", "--skip-git-repo-check", "--cd", ws] + argv_extra + ["-"]
    env = {**os.environ, "CODEX_HOME": home}
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30,
                              stdin=subprocess.DEVNULL, env=env)
        err = (proc.stderr or proc.stdout).strip().splitlines()
        tail = err[-1][:200] if err else "(no output)"
        print(f"{label}\n  exit={proc.returncode}  last-line: {tail}\n")
    except subprocess.TimeoutExpired:
        print(f"{label}\n  TIMEOUT (killed at 30s — treat as got-past-config)\n")


ACT = ['-c', 'default_permissions="exec_loop_wall"']

run("A. bad-TOML profile file, NO --ignore-user-config (is the file read at all?)",
    {"tp.config.toml": BAD_TOML},
    ["--profile", "tp"] + ACT)

run("B. bad-TOML profile file, WITH --ignore-user-config (does the flag suppress it?)",
    {"tp.config.toml": BAD_TOML},
    ["--ignore-user-config", "--profile", "tp"] + ACT)

run("C. good profile file, WITH --ignore-user-config + --strict-config (the launcher's exact combo)",
    {"tp.config.toml": GOOD_TOML},
    ["--ignore-user-config", "--strict-config", "--profile", "tp"] + ACT)

run("D. good profile file, NO --ignore-user-config, WITH --strict-config",
    {"tp.config.toml": GOOD_TOML},
    ["--strict-config", "--profile", "tp"] + ACT)

run("E. good [permissions] table directly in config.toml, WITH --strict-config (no --profile at all)",
    {"config.toml": GOOD_TOML},
    ["--strict-config"] + ACT)
