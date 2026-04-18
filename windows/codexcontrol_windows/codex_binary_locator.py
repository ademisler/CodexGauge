from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def resolve() -> str | None:
    binary = shutil.which("codex")
    if binary:
        return binary

    for candidate in _path_candidates():
        if candidate.is_file():
            return str(candidate)

    try:
        output = subprocess.check_output(
            ["where.exe", "codex"],
            text=True,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    for line in output.splitlines():
        candidate = line.strip()
        if candidate:
            return candidate

    return None


def _path_candidates() -> list[Path]:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    home = Path.home()
    return [
        local_app_data / "OpenAI" / "Codex" / "bin" / "codex.exe",
        home / ".bun" / "bin" / "codex.exe",
        home / "AppData" / "Local" / "Microsoft" / "WindowsApps" / "codex.exe",
    ]
