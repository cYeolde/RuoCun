"""Run one engineering command with a synthetic home, config, and temp directory."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--state", type=Path, default=Path(".cache/engineering"))
    parser.add_argument("--wheelhouse", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command: list[str] = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("an explicit command is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.label):
        parser.error("--label may only contain letters, digits, hyphens, and underscores")

    executable = Path(command[0]).resolve()
    command[0] = str(executable)
    state = args.state.resolve()
    for part in ("home", "appdata", "localappdata", "tmp", "raw", "pip-cache"):
        (state / part).mkdir(parents=True, exist_ok=True)
    env = {
        "PATH": str(executable.parent),
        "HOME": str(state / "home"),
        "USERPROFILE": str(state / "home"),
        "APPDATA": str(state / "appdata"),
        "LOCALAPPDATA": str(state / "localappdata"),
        "TEMP": str(state / "tmp"),
        "TMP": str(state / "tmp"),
        "PYTHONUTF8": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONSAFEPATH": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PIP_CONFIG_FILE": os.devnull,
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PIP_NO_INPUT": "1",
        "PIP_CACHE_DIR": str(state / "pip-cache"),
    }
    if os.name == "nt":
        windows = Path(os.environ.get("SYSTEMROOT", "C:/Windows"))
        system = windows / "System32"
        env.update(
            SYSTEMROOT=str(windows),
            WINDIR=str(windows),
            COMSPEC=str(system / "cmd.exe"),
            PATH=os.pathsep.join((env["PATH"], str(system))),
            PATHEXT=".COM;.EXE;.BAT;.CMD",
        )
    if args.wheelhouse:
        env.update(PIP_NO_INDEX="1", PIP_FIND_LINKS=args.wheelhouse.resolve().as_uri())

    raw = state / "raw" / args.label
    raw.mkdir(exist_ok=False)
    result = subprocess.run(command, cwd=args.cwd.resolve(), env=env, capture_output=True)
    parent_credentials = [
        value.encode()
        for name, value in os.environ.items()
        if re.search(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL", name, re.I)
        and len(value) >= 8
    ]
    sensitive_match = any(
        value in result.stdout or value in result.stderr for value in parent_credentials
    )
    if not sensitive_match:
        (raw / "stdout.bin").write_bytes(result.stdout)
        (raw / "stderr.bin").write_bytes(result.stderr)
    receipt = {
        "exit": result.returncode,
        "environment": "explicit allowlist with synthetic HOME, config, and temp",
        "sensitive_match": sensitive_match,
    }
    (raw / "command.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": args.label, **receipt}))
    return 90 if sensitive_match else result.returncode


if __name__ == "__main__":
    sys.exit(main())
