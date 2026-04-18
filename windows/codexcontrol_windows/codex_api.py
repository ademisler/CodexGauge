from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from .models import AccountUsageSnapshot, CreditsBalanceSnapshot, StoredAccount, UsageWindowSnapshot, parse_datetime


REFRESH_ENDPOINT = "https://auth.openai.com/oauth/token"
USAGE_DEFAULT_BASE = "https://chatgpt.com/backend-api"
REFRESH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
REQUEST_TIMEOUT_SECONDS = 30


class CodexApiError(RuntimeError):
    """Friendly error surfaced to the UI."""


@dataclass(slots=True)
class AuthBackedIdentity:
    email: str | None
    auth_subject: str | None
    plan: str | None
    provider_account_id: str | None


@dataclass(slots=True)
class AuthCredentials:
    access_token: str
    refresh_token: str
    id_token: str | None
    account_id: str | None
    last_refresh: datetime | None

    @property
    def needs_refresh(self) -> bool:
        if self.last_refresh is None:
            return True
        return datetime.now(timezone.utc) - self.last_refresh > timedelta(days=8)


def load_identity(codex_home_path: str) -> AuthBackedIdentity:
    credentials = _load_credentials(codex_home_path)
    payload = _parse_jwt(credentials.id_token) if credentials.id_token else None
    auth = payload.get("https://api.openai.com/auth") if isinstance(payload, dict) else None
    profile = payload.get("https://api.openai.com/profile") if isinstance(payload, dict) else None

    auth = auth if isinstance(auth, dict) else {}
    profile = profile if isinstance(profile, dict) else {}

    email = _normalize_string(payload.get("email") if isinstance(payload, dict) else None) or _normalize_string(profile.get("email"))
    auth_subject = _normalize_string(payload.get("sub") if isinstance(payload, dict) else None)
    plan = _normalize_string(auth.get("chatgpt_plan_type")) or _normalize_string(
        payload.get("chatgpt_plan_type") if isinstance(payload, dict) else None
    )
    provider_account_id = _normalize_string(credentials.account_id) or _normalize_string(
        auth.get("chatgpt_account_id")
    ) or _normalize_string(payload.get("chatgpt_account_id") if isinstance(payload, dict) else None)

    return AuthBackedIdentity(
        email=email,
        auth_subject=auth_subject,
        plan=plan,
        provider_account_id=provider_account_id,
    )


def fetch_snapshot(account: StoredAccount) -> AccountUsageSnapshot:
    credentials = _load_credentials(account.codex_home_path)

    if credentials.needs_refresh and credentials.refresh_token:
        credentials = _refresh(credentials)
        _save_credentials(credentials, account.codex_home_path)

    try:
        return _fetch_verified_snapshot(
            codex_home_path=account.codex_home_path,
            credentials=credentials,
            fallback_email=account.email_hint,
        )
    except CodexApiError as error:
        if str(error) != "The Codex usage API request returned unauthorized." or not credentials.refresh_token:
            raise

    credentials = _refresh(credentials)
    _save_credentials(credentials, account.codex_home_path)
    return _fetch_verified_snapshot(
        codex_home_path=account.codex_home_path,
        credentials=credentials,
        fallback_email=account.email_hint,
    )


def _fetch_verified_snapshot(
    codex_home_path: str,
    credentials: AuthCredentials,
    fallback_email: str | None,
) -> AccountUsageSnapshot:
    first = _fetch_snapshot(codex_home_path, credentials, fallback_email)
    second = _fetch_snapshot(codex_home_path, credentials, fallback_email)

    if _is_equivalent(first, second):
        return second

    third = _fetch_snapshot(codex_home_path, credentials, fallback_email)
    if _is_equivalent(first, third) or _is_equivalent(second, third):
        return third

    raise CodexApiError("Live API responses were inconsistent. The data could not be verified.")


def _fetch_snapshot(
    codex_home_path: str,
    credentials: AuthCredentials,
    fallback_email: str | None,
) -> AccountUsageSnapshot:
    identity: AuthBackedIdentity | None
    try:
        identity = load_identity(codex_home_path)
    except CodexApiError:
        identity = None

    response = _fetch_usage(
        access_token=credentials.access_token,
        account_id=credentials.account_id,
        codex_home_path=codex_home_path,
    )
    primary_window, secondary_window = _make_normalized_windows(response.get("rate_limit"))
    credits = response.get("credits")

    return AccountUsageSnapshot(
        email=(identity.email if identity else None) or fallback_email,
        provider_account_id=(identity.provider_account_id if identity else None) or credentials.account_id,
        plan=_normalize_string(response.get("plan_type")) or (identity.plan if identity else None),
        allowed=response.get("rate_limit", {}).get("allowed") if isinstance(response.get("rate_limit"), dict) else None,
        limit_reached=response.get("rate_limit", {}).get("limit_reached") if isinstance(response.get("rate_limit"), dict) else None,
        primary_window=primary_window,
        secondary_window=secondary_window,
        credits=_make_credits(credits) if isinstance(credits, dict) else None,
        updated_at=datetime.now(timezone.utc),
    )


def _load_credentials(codex_home_path: str) -> AuthCredentials:
    auth_path = Path(codex_home_path) / "auth.json"
    if not auth_path.exists():
        raise CodexApiError("No `auth.json` was found for this account.")

    try:
        payload = json.loads(auth_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise CodexApiError(f"Failed to read the auth file: {error}") from error

    api_key = payload.get("OPENAI_API_KEY")
    if isinstance(api_key, str) and api_key.strip():
        return AuthCredentials(
            access_token=api_key.strip(),
            refresh_token="",
            id_token=None,
            account_id=None,
            last_refresh=None,
        )

    tokens = payload.get("tokens")
    if not isinstance(tokens, dict):
        raise CodexApiError("The required token fields are missing from `auth.json`.")

    access_token = _string_value(tokens, "access_token")
    if not access_token:
        raise CodexApiError("The required token fields are missing from `auth.json`.")

    return AuthCredentials(
        access_token=access_token,
        refresh_token=_string_value(tokens, "refresh_token") or "",
        id_token=_string_value(tokens, "id_token"),
        account_id=_string_value(tokens, "account_id"),
        last_refresh=parse_datetime(payload.get("last_refresh")),
    )


def _save_credentials(credentials: AuthCredentials, codex_home_path: str) -> None:
    auth_path = Path(codex_home_path) / "auth.json"
    payload: dict[str, Any] = {}
    if auth_path.exists():
        try:
            payload = json.loads(auth_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}

    tokens: dict[str, Any] = {
        "access_token": credentials.access_token,
        "refresh_token": credentials.refresh_token,
    }
    if credentials.id_token is not None:
        tokens["id_token"] = credentials.id_token
    if credentials.account_id is not None:
        tokens["account_id"] = credentials.account_id

    payload["tokens"] = tokens
    payload["last_refresh"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    auth_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _refresh(credentials: AuthCredentials) -> AuthCredentials:
    body = {
        "client_id": REFRESH_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": credentials.refresh_token,
        "scope": "openid profile email",
    }
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    }

    try:
        response = requests.post(
            REFRESH_ENDPOINT,
            json=body,
            headers=headers,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as error:
        raise CodexApiError(f"Network error: {error}") from error

    if response.status_code == 401:
        code = _extract_error_code(response.text).lower() if response.text else ""
        if code == "refresh_token_reused":
            raise CodexApiError("The refresh token can no longer be reused. Sign in again for this account.")
        if code == "refresh_token_invalidated":
            raise CodexApiError("The refresh token was revoked. Sign in again for this account.")
        raise CodexApiError("The refresh token has expired. Sign in again for this account.")

    if response.status_code != 200:
        raise CodexApiError("The Codex API response was not in the expected format.")

    try:
        payload = response.json()
    except ValueError as error:
        raise CodexApiError("The Codex API response was not in the expected format.") from error

    if not isinstance(payload, dict):
        raise CodexApiError("The Codex API response was not in the expected format.")

    return AuthCredentials(
        access_token=str(payload.get("access_token") or credentials.access_token),
        refresh_token=str(payload.get("refresh_token") or credentials.refresh_token),
        id_token=payload.get("id_token") or credentials.id_token,
        account_id=credentials.account_id,
        last_refresh=datetime.now(timezone.utc),
    )


def _fetch_usage(access_token: str, account_id: str | None, codex_home_path: str) -> dict[str, Any]:
    url = _resolve_usage_url(codex_home_path)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "codex-cli",
        "Accept": "application/json",
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as error:
        raise CodexApiError(f"Network error: {error}") from error

    if 200 <= response.status_code <= 299:
        try:
            payload = response.json()
        except ValueError as error:
            raise CodexApiError("The Codex API response was not in the expected format.") from error
        if isinstance(payload, dict):
            return payload
        raise CodexApiError("The Codex API response was not in the expected format.")

    if response.status_code in (401, 403):
        raise CodexApiError("The Codex usage API request returned unauthorized.")

    message = response.text.strip()
    if message:
        raise CodexApiError(f"Codex API error {response.status_code}: {message}")
    raise CodexApiError(f"Codex API error {response.status_code}.")


def _resolve_usage_url(codex_home_path: str) -> str:
    config_path = Path(codex_home_path) / "config.toml"
    configured_base: str | None = None
    if config_path.exists():
        configured_base = _parse_chatgpt_base_url(config_path.read_text(encoding="utf-8"))

    base = (configured_base or USAGE_DEFAULT_BASE).strip()
    while base.endswith("/"):
        base = base[:-1]

    if base.startswith("https://chatgpt.com") and "/backend-api" not in base:
        base += "/backend-api"
    if base.startswith("https://chat.openai.com") and "/backend-api" not in base:
        base += "/backend-api"

    path = "/wham/usage" if "/backend-api" in base else "/api/codex/usage"
    return f"{base}{path}"


def _parse_chatgpt_base_url(contents: str) -> str | None:
    for raw_line in contents.splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if not line:
            continue

        parts = line.split("=", maxsplit=1)
        if len(parts) != 2 or parts[0].strip() != "chatgpt_base_url":
            continue

        value = parts[1].strip()
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1]
        if value.startswith("'") and value.endswith("'") and len(value) >= 2:
            value = value[1:-1]
        return value

    return None


def _extract_error_code(payload: str) -> str:
    try:
        parsed = json.loads(payload)
    except ValueError:
        return ""

    if not isinstance(parsed, dict):
        return ""

    error = parsed.get("error")
    if isinstance(error, dict):
        code = error.get("code")
        return str(code) if code else ""
    if isinstance(error, str):
        return error
    code = parsed.get("code")
    return str(code) if code else ""


def _make_window(payload: dict[str, Any]) -> UsageWindowSnapshot:
    return UsageWindowSnapshot(
        used_percent=float(payload["used_percent"]),
        reset_at=datetime.fromtimestamp(float(payload["reset_at"]), tz=timezone.utc),
        limit_window_seconds=int(payload["limit_window_seconds"]),
    )


def _make_credits(payload: dict[str, Any]) -> CreditsBalanceSnapshot:
    balance = payload.get("balance")
    return CreditsBalanceSnapshot(
        has_credits=bool(payload.get("has_credits")),
        unlimited=bool(payload.get("unlimited")),
        balance=float(balance) if balance is not None else None,
    )


def _is_equivalent(left: AccountUsageSnapshot, right: AccountUsageSnapshot) -> bool:
    return (
        (_normalize_string(left.email) or "").lower() == (_normalize_string(right.email) or "").lower()
        and _normalize_string(left.provider_account_id) == _normalize_string(right.provider_account_id)
        and _normalize_string(left.plan) == _normalize_string(right.plan)
        and left.allowed == right.allowed
        and left.limit_reached == right.limit_reached
        and _windows_equivalent(left.primary_window, right.primary_window)
        and _windows_equivalent(left.secondary_window, right.secondary_window)
        and _credits_equivalent(left.credits, right.credits)
    )


def _windows_equivalent(left: UsageWindowSnapshot | None, right: UsageWindowSnapshot | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False

    if left.reset_at is None and right.reset_at is None:
        reset_matches = True
    elif left.reset_at is not None and right.reset_at is not None:
        reset_matches = abs((left.reset_at - right.reset_at).total_seconds()) <= 1
    else:
        reset_matches = False

    return (
        left.limit_window_seconds == right.limit_window_seconds
        and reset_matches
        and abs(left.used_percent - right.used_percent) < 0.001
    )


def _credits_equivalent(left: CreditsBalanceSnapshot | None, right: CreditsBalanceSnapshot | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False

    if left.balance is None and right.balance is None:
        balances_match = True
    elif left.balance is not None and right.balance is not None:
        balances_match = abs(left.balance - right.balance) < 0.001
    else:
        balances_match = False

    return (
        left.has_credits == right.has_credits
        and left.unlimited == right.unlimited
        and balances_match
    )


def _make_normalized_windows(rate_limit: Any) -> tuple[UsageWindowSnapshot | None, UsageWindowSnapshot | None]:
    if not isinstance(rate_limit, dict):
        return None, None

    primary = _make_window(rate_limit["primary_window"]) if isinstance(rate_limit.get("primary_window"), dict) else None
    secondary = _make_window(rate_limit["secondary_window"]) if isinstance(rate_limit.get("secondary_window"), dict) else None

    if rate_limit.get("limit_reached") is True:
        if primary is not None:
            primary = UsageWindowSnapshot(
                used_percent=100.0,
                reset_at=primary.reset_at,
                limit_window_seconds=primary.limit_window_seconds,
            )
        if secondary is not None:
            secondary = UsageWindowSnapshot(
                used_percent=100.0,
                reset_at=secondary.reset_at,
                limit_window_seconds=secondary.limit_window_seconds,
            )

    return _normalize_window_roles(primary, secondary)


def _normalize_window_roles(
    primary: UsageWindowSnapshot | None,
    secondary: UsageWindowSnapshot | None,
) -> tuple[UsageWindowSnapshot | None, UsageWindowSnapshot | None]:
    if primary is not None and secondary is not None:
        primary_role = _role_for_window(primary)
        secondary_role = _role_for_window(secondary)

        if (primary_role, secondary_role) in {
            ("session", "weekly"),
            ("session", "unknown"),
            ("unknown", "weekly"),
        }:
            return primary, secondary
        if (primary_role, secondary_role) in {
            ("weekly", "session"),
            ("weekly", "unknown"),
        }:
            return secondary, primary
        return primary, secondary

    if primary is not None:
        if _role_for_window(primary) == "weekly":
            return None, primary
        return primary, None

    if secondary is not None:
        if _role_for_window(secondary) == "weekly":
            return None, secondary
        return secondary, None

    return None, None


def _role_for_window(window: UsageWindowSnapshot) -> str:
    if window.limit_window_seconds == 18_000:
        return "session"
    if window.limit_window_seconds == 604_800:
        return "weekly"
    return "unknown"


def _string_value(dictionary: dict[str, Any], key: str) -> str | None:
    value = dictionary.get(key)
    if isinstance(value, str) and value:
        return value

    pieces = key.split("_")
    camel_key = pieces[0].lower() + "".join(piece[:1].upper() + piece[1:].lower() for piece in pieces[1:])
    value = dictionary.get(camel_key)
    if isinstance(value, str) and value:
        return value
    return None


def _normalize_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _parse_jwt(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None

    parts = token.split(".")
    if len(parts) < 2:
        return None

    payload = parts[1]
    payload += "=" * (-len(payload) % 4)

    try:
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        parsed = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None

    return parsed if isinstance(parsed, dict) else None
