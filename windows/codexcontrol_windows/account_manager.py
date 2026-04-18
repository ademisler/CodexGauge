from __future__ import annotations

import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import codex_binary_locator
from .codex_api import AuthBackedIdentity, CodexApiError, load_identity
from .file_locations import AMBIENT_CODEX_HOME, AUTH_BACKUPS_DIRECTORY, MANAGED_HOMES_DIRECTORY, ensure_directories
from .models import StoredAccount, StoredAccountSource, utc_now


class CodexAccountManagerError(RuntimeError):
    """Friendly account manager error."""


@dataclass(slots=True)
class CodexLoginResult:
    outcome: str
    output: str


@dataclass(slots=True)
class CodexSwitchResult:
    materialized_account: StoredAccount | None
    backup_path: str | None
    ambient_account: StoredAccount | None


class ManagedLoginProcess:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._cancelled = False

    def bind(self, process: subprocess.Popen[str]) -> None:
        with self._lock:
            self._process = process
            self._cancelled = False

    def clear(self) -> None:
        with self._lock:
            self._process = None

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def cancel(self) -> None:
        with self._lock:
            process = self._process
            self._cancelled = True

        if process is None or process.poll() is not None:
            return

        try:
            process.send_signal(signal.SIGINT)
        except OSError:
            pass

        try:
            process.terminate()
            process.wait(timeout=0.75)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
            except OSError:
                pass


class CodexLoginRunner:
    @staticmethod
    def run(home_path: str, timeout: float = 180, handle: ManagedLoginProcess | None = None) -> CodexLoginResult:
        active_handle = handle or ManagedLoginProcess()
        binary = codex_binary_locator.resolve()
        if not binary:
            return CodexLoginResult(outcome="missing_binary", output="")

        env = os.environ.copy()
        env["CODEX_HOME"] = home_path

        try:
            process = subprocess.Popen(
                [binary, "login"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
        except OSError as error:
            return CodexLoginResult(outcome="launch_failed", output=str(error))

        active_handle.bind(process)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                process.terminate()
                process.wait(timeout=0.75)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    process.kill()
                except OSError:
                    pass
            stdout, stderr = _read_remaining_output(process)
            active_handle.clear()
            return CodexLoginResult(outcome="timed_out", output=_combine_output(stdout, stderr))

        active_handle.clear()
        output = _combine_output(stdout, stderr)
        if active_handle.cancelled:
            return CodexLoginResult(outcome="cancelled", output=output)
        if process.returncode == 0:
            return CodexLoginResult(outcome="success", output=output)
        return CodexLoginResult(outcome="failed", output=output)


class CodexAccountManager:
    def add_managed_account(self, handle: ManagedLoginProcess | None = None) -> StoredAccount:
        ensure_directories()
        home_path = MANAGED_HOMES_DIRECTORY / str(uuid4())
        home_path.mkdir(parents=True, exist_ok=True)

        try:
            return self._authenticate_account(home_path, StoredAccountSource.MANAGED_BY_APP, handle=handle)
        except Exception:
            shutil.rmtree(home_path, ignore_errors=True)
            raise

    def reauthenticate(self, account: StoredAccount, handle: ManagedLoginProcess | None = None) -> StoredAccount:
        return self._authenticate_account(
            Path(account.codex_home_path),
            account.source,
            existing=account,
            handle=handle,
        )

    def remove_managed_files_if_owned(self, account: StoredAccount) -> None:
        if not account.source.owns_files:
            return

        root = MANAGED_HOMES_DIRECTORY.resolve(strict=False)
        target = Path(account.codex_home_path).resolve(strict=False)

        try:
            target.relative_to(root)
        except ValueError as error:
            raise CodexAccountManagerError("This path is not an app-managed home directory.") from error

        if target.exists():
            shutil.rmtree(target, ignore_errors=False)

    def discover_managed_accounts(self, existing: list[StoredAccount]) -> list[StoredAccount]:
        ensure_directories()
        discovered: list[StoredAccount] = []
        for home_path in sorted(MANAGED_HOMES_DIRECTORY.iterdir(), key=lambda item: item.name.lower()):
            candidate = self._discovered_managed_account(home_path, existing)
            if candidate is not None:
                discovered.append(candidate)
        return discovered

    def discover_ambient_account(self, existing: list[StoredAccount]) -> StoredAccount | None:
        home_path = AMBIENT_CODEX_HOME
        auth_path = home_path / "auth.json"
        if not home_path.is_dir() or not auth_path.exists():
            return None

        try:
            identity = load_identity(str(home_path))
        except CodexApiError:
            return None

        if not identity.email and not identity.provider_account_id:
            return None

        discovered_at = _directory_timestamp(home_path)
        candidate = StoredAccount(
            id=uuid4(),
            nickname=None,
            email_hint=identity.email,
            auth_subject=identity.auth_subject,
            provider_account_id=identity.provider_account_id,
            codex_home_path=str(home_path),
            source=StoredAccountSource.AMBIENT,
            created_at=discovered_at,
            updated_at=discovered_at,
            last_authenticated_at=discovered_at,
        )

        matched_existing = next((account for account in existing if account.matches(candidate)), None)
        return StoredAccount(
            id=matched_existing.id if matched_existing else uuid4(),
            nickname=matched_existing.nickname if matched_existing else None,
            email_hint=identity.email or (matched_existing.email_hint if matched_existing else None),
            auth_subject=identity.auth_subject or (matched_existing.auth_subject if matched_existing else None),
            provider_account_id=identity.provider_account_id or (
                matched_existing.provider_account_id if matched_existing else None
            ),
            codex_home_path=str(home_path),
            source=StoredAccountSource.AMBIENT,
            created_at=matched_existing.created_at if matched_existing else discovered_at,
            updated_at=max(
                matched_existing.updated_at if matched_existing else discovered_at,
                discovered_at,
            ),
            last_authenticated_at=matched_existing.last_authenticated_at if matched_existing else discovered_at,
        )

    def load_active_identity(self) -> AuthBackedIdentity | None:
        auth_path = AMBIENT_CODEX_HOME / "auth.json"
        if not auth_path.exists():
            return None

        try:
            return load_identity(str(AMBIENT_CODEX_HOME))
        except CodexApiError:
            return None

    def switch_active_account(self, target: StoredAccount, existing: list[StoredAccount]) -> CodexSwitchResult:
        ensure_directories()

        target_auth_path = Path(target.codex_home_path) / "auth.json"
        if not target_auth_path.exists():
            raise CodexAccountManagerError("The selected account does not contain `auth.json`.")

        ambient_account = self.discover_ambient_account(existing)
        materialized_account: StoredAccount | None = None
        if ambient_account is not None and ambient_account.source is StoredAccountSource.AMBIENT and not ambient_account.matches(target):
            materialized_account = self.materialize_as_managed(ambient_account)

        AMBIENT_CODEX_HOME.mkdir(parents=True, exist_ok=True)
        backup_path = self._backup_ambient_auth()
        shutil.copy2(target_auth_path, AMBIENT_CODEX_HOME / "auth.json")

        return CodexSwitchResult(
            materialized_account=materialized_account,
            backup_path=backup_path,
            ambient_account=self.discover_ambient_account(existing),
        )

    def materialize_as_managed(self, account: StoredAccount) -> StoredAccount:
        ensure_directories()

        source_auth_path = Path(account.codex_home_path) / "auth.json"
        if not source_auth_path.exists():
            raise CodexAccountManagerError("The current active account does not contain `auth.json`.")

        destination_home = MANAGED_HOMES_DIRECTORY / str(uuid4())
        destination_home.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_auth_path, destination_home / "auth.json")

        now = utc_now()
        return StoredAccount(
            id=account.id,
            nickname=account.nickname,
            email_hint=account.email_hint,
            auth_subject=account.auth_subject,
            provider_account_id=account.provider_account_id,
            codex_home_path=str(destination_home),
            source=StoredAccountSource.MANAGED_BY_APP,
            created_at=account.created_at,
            updated_at=now,
            last_authenticated_at=account.last_authenticated_at or now,
        )

    def _backup_ambient_auth(self) -> str | None:
        ensure_directories()
        auth_path = AMBIENT_CODEX_HOME / "auth.json"
        if not auth_path.exists():
            return None

        backup_path = AUTH_BACKUPS_DIRECTORY / f"ambient-auth-{_timestamp_slug()}.json"
        shutil.copy2(auth_path, backup_path)
        return str(backup_path)

    def _authenticate_account(
        self,
        home_path: Path,
        source: StoredAccountSource,
        existing: StoredAccount | None = None,
        handle: ManagedLoginProcess | None = None,
    ) -> StoredAccount:
        result = CodexLoginRunner.run(str(home_path), handle=handle)

        if result.outcome == "cancelled":
            raise CodexAccountManagerError("Account setup cancelled.")
        if result.outcome == "missing_binary":
            raise CodexAccountManagerError("The `codex` command could not be found.")
        if result.outcome == "timed_out":
            raise CodexAccountManagerError("The Codex sign-in flow timed out.")
        if result.outcome == "launch_failed":
            raise CodexAccountManagerError(f"Failed to start the Codex sign-in flow: {result.output}")
        if result.outcome == "failed":
            raise CodexAccountManagerError(f"The Codex sign-in flow did not complete.\n{result.output}")

        try:
            identity = load_identity(str(home_path))
        except CodexApiError as error:
            raise CodexAccountManagerError(str(error)) from error

        if not identity.email and not identity.provider_account_id:
            raise CodexAccountManagerError("Sign-in completed, but the account identity could not be read.")

        now = utc_now()
        return StoredAccount(
            id=existing.id if existing else uuid4(),
            nickname=existing.nickname if existing else None,
            email_hint=identity.email or (existing.email_hint if existing else None),
            auth_subject=identity.auth_subject or (existing.auth_subject if existing else None),
            provider_account_id=identity.provider_account_id or (existing.provider_account_id if existing else None),
            codex_home_path=str(home_path),
            source=source,
            created_at=existing.created_at if existing else now,
            updated_at=now,
            last_authenticated_at=now,
        )

    def _discovered_managed_account(self, home_path: Path, existing: list[StoredAccount]) -> StoredAccount | None:
        if not home_path.is_dir():
            return None

        auth_path = home_path / "auth.json"
        if not auth_path.exists():
            return None

        try:
            identity = load_identity(str(home_path))
        except CodexApiError:
            return None

        if not identity.email and not identity.provider_account_id:
            return None

        discovered_at = _directory_timestamp(home_path)
        candidate = StoredAccount(
            id=uuid4(),
            nickname=None,
            email_hint=identity.email,
            auth_subject=identity.auth_subject,
            provider_account_id=identity.provider_account_id,
            codex_home_path=str(home_path),
            source=StoredAccountSource.MANAGED_BY_APP,
            created_at=discovered_at,
            updated_at=discovered_at,
            last_authenticated_at=discovered_at,
        )

        matched_existing = next((account for account in existing if account.matches(candidate)), None)
        return StoredAccount(
            id=matched_existing.id if matched_existing else uuid4(),
            nickname=matched_existing.nickname if matched_existing else None,
            email_hint=identity.email or (matched_existing.email_hint if matched_existing else None),
            auth_subject=identity.auth_subject or (matched_existing.auth_subject if matched_existing else None),
            provider_account_id=identity.provider_account_id or (
                matched_existing.provider_account_id if matched_existing else None
            ),
            codex_home_path=str(home_path),
            source=StoredAccountSource.MANAGED_BY_APP,
            created_at=matched_existing.created_at if matched_existing else discovered_at,
            updated_at=max(
                matched_existing.updated_at if matched_existing else discovered_at,
                discovered_at,
            ),
            last_authenticated_at=max(
                matched_existing.last_authenticated_at if matched_existing and matched_existing.last_authenticated_at else discovered_at,
                discovered_at,
            ),
        )


def _combine_output(stdout: str | None, stderr: str | None) -> str:
    merged = "\n".join(part.strip() for part in (stdout or "", stderr or "") if part and part.strip()).strip()
    return merged[:4000] if merged else "No output captured."


def _read_remaining_output(process: subprocess.Popen[str]) -> tuple[str, str]:
    stdout = ""
    stderr = ""
    for _ in range(5):
        if process.poll() is not None:
            break
        time.sleep(0.1)

    if process.stdout is not None:
        try:
            stdout = process.stdout.read()
        except OSError:
            stdout = ""
    if process.stderr is not None:
        try:
            stderr = process.stderr.read()
        except OSError:
            stderr = ""
    return stdout, stderr


def _directory_timestamp(path: Path):
    stat = path.stat()
    return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)


def _timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%d-%H%M%S")
