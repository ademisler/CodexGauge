from __future__ import annotations

import os
import shutil
from pathlib import Path


def appdata_directory() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata)
    return Path.home() / "AppData" / "Roaming"


APP_SUPPORT_DIRECTORY = appdata_directory() / "CodexControl"
LEGACY_APP_SUPPORT_DIRECTORIES = [
    appdata_directory() / "".join(["Codex", "Gauge"]),
    appdata_directory() / "".join(["Codex", "Accounts"]),
]
ACCOUNTS_FILE = APP_SUPPORT_DIRECTORY / "accounts.json"
SNAPSHOTS_FILE = APP_SUPPORT_DIRECTORY / "snapshots.json"
MANAGED_HOMES_DIRECTORY = APP_SUPPORT_DIRECTORY / "managed-homes"
AUTH_BACKUPS_DIRECTORY = APP_SUPPORT_DIRECTORY / "auth-backups"
AMBIENT_CODEX_HOME = Path.home() / ".codex"


def ensure_directories() -> None:
    if not APP_SUPPORT_DIRECTORY.exists():
        for legacy_directory in LEGACY_APP_SUPPORT_DIRECTORIES:
            if legacy_directory.exists():
                shutil.move(str(legacy_directory), str(APP_SUPPORT_DIRECTORY))
                break

    APP_SUPPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    MANAGED_HOMES_DIRECTORY.mkdir(parents=True, exist_ok=True)
    AUTH_BACKUPS_DIRECTORY.mkdir(parents=True, exist_ok=True)
