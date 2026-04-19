from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Iterable
from uuid import UUID

from .file_locations import ACCOUNTS_FILE, SNAPSHOTS_FILE, ensure_directories
from .models import AccountUsageSnapshot, StoredAccount


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character)).casefold()


class AccountStore:
    current_version = 1

    def load_accounts(self) -> list[StoredAccount]:
        if not ACCOUNTS_FILE.exists():
            return []

        payload = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        accounts = [StoredAccount.from_dict(item) for item in payload.get("accounts", [])]
        return self._sorted(accounts)

    def save_accounts(self, accounts: Iterable[StoredAccount]) -> None:
        ensure_directories()
        payload = {
            "version": self.current_version,
            "accounts": [account.to_dict() for account in self._sorted(list(accounts))],
        }
        ACCOUNTS_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def merge(self, existing: list[StoredAccount], incoming: list[StoredAccount]) -> list[StoredAccount]:
        result = list(existing)
        for candidate in incoming:
            match_index = next((index for index, account in enumerate(result) if account.matches(candidate)), None)
            if match_index is None:
                result.append(candidate)
                continue

            merged = result[match_index]
            merged.merge_from(candidate)
            result[match_index] = merged

        return self._sorted(result)

    def _sorted(self, accounts: list[StoredAccount]) -> list[StoredAccount]:
        return sorted(accounts, key=lambda account: _fold_text(account.display_name))


class SnapshotStore:
    def load(self) -> dict[UUID, AccountUsageSnapshot]:
        if not SNAPSHOTS_FILE.exists():
            return {}

        payload = json.loads(SNAPSHOTS_FILE.read_text(encoding="utf-8"))
        snapshots = payload.get("snapshots", {})
        result: dict[UUID, AccountUsageSnapshot] = {}
        for key, value in snapshots.items():
            result[UUID(str(key))] = AccountUsageSnapshot.from_dict(value)
        return result

    def save(self, snapshots: dict[UUID, AccountUsageSnapshot]) -> None:
        ensure_directories()
        payload = {
            "snapshots": {
                str(account_id): snapshot.to_dict()
                for account_id, snapshot in snapshots.items()
            }
        }
        SNAPSHOTS_FILE.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
