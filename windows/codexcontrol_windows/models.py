from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


LEGACY_IMPORTED_VALUE = "".join(["imported", "Codex", "Bar"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None

    text = str(value).strip()
    if not text:
        return None

    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"

    return datetime.fromisoformat(text)


def format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_identifier(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    return normalized or None


def max_datetime(left: datetime | None, right: datetime | None) -> datetime | None:
    values = [candidate for candidate in (left, right) if candidate is not None]
    return max(values) if values else None


class StoredAccountSource(str, Enum):
    AMBIENT = "ambient"
    MANAGED_BY_APP = "managedByApp"

    @classmethod
    def from_raw(cls, value: str) -> "StoredAccountSource":
        if value == cls.AMBIENT.value:
            return cls.AMBIENT
        if value in (cls.MANAGED_BY_APP.value, LEGACY_IMPORTED_VALUE):
            return cls.MANAGED_BY_APP
        raise ValueError(f"Unknown stored account source: {value}")

    @property
    def display_name(self) -> str:
        if self is StoredAccountSource.AMBIENT:
            return "System"
        return "Managed"

    @property
    def owns_files(self) -> bool:
        return self is StoredAccountSource.MANAGED_BY_APP


@dataclass(slots=True)
class StoredAccount:
    id: UUID
    nickname: str | None
    email_hint: str | None
    auth_subject: str | None
    provider_account_id: str | None
    codex_home_path: str
    source: StoredAccountSource
    created_at: datetime
    updated_at: datetime
    last_authenticated_at: datetime | None = None

    @property
    def display_name(self) -> str:
        if self.nickname and self.nickname.strip():
            return self.nickname.strip()
        if self.email_hint:
            return self.email_hint
        return os.path.basename(os.path.normpath(self.codex_home_path))

    @property
    def normalized_email_hint(self) -> str | None:
        return normalize_identifier(self.email_hint)

    @property
    def normalized_auth_subject(self) -> str | None:
        return normalize_identifier(self.auth_subject)

    @property
    def standardized_home_path(self) -> str:
        return os.path.normcase(os.path.abspath(os.path.normpath(self.codex_home_path)))

    @property
    def source_priority(self) -> int:
        if self.source is StoredAccountSource.MANAGED_BY_APP:
            return 2
        return 1

    @property
    def recency_date(self) -> datetime:
        return self.last_authenticated_at or self.updated_at

    def matches(self, other: "StoredAccount") -> bool:
        if self.normalized_auth_subject and self.normalized_auth_subject == other.normalized_auth_subject:
            return True
        if self.standardized_home_path == other.standardized_home_path:
            return True
        if self.normalized_email_hint and self.normalized_email_hint == other.normalized_email_hint:
            return True
        return False

    def merge_from(self, other: "StoredAccount") -> None:
        if not self.nickname or not self.nickname.strip():
            self.nickname = other.nickname

        prefer_other_identity = other.source_priority > self.source_priority or (
            other.source_priority == self.source_priority and other.recency_date >= self.recency_date
        )

        if prefer_other_identity and other.email_hint and other.email_hint.strip():
            self.email_hint = other.email_hint.strip()
        elif not self.email_hint:
            self.email_hint = other.email_hint

        if prefer_other_identity and other.auth_subject and other.auth_subject.strip():
            self.auth_subject = other.auth_subject.strip()
        elif not self.auth_subject:
            self.auth_subject = other.auth_subject

        if prefer_other_identity and other.provider_account_id and other.provider_account_id.strip():
            self.provider_account_id = other.provider_account_id.strip()
        elif not self.provider_account_id:
            self.provider_account_id = other.provider_account_id

        if prefer_other_identity:
            self.source = other.source
            self.codex_home_path = other.codex_home_path

        self.updated_at = max(self.updated_at, other.updated_at)
        self.last_authenticated_at = max_datetime(self.last_authenticated_at, other.last_authenticated_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "nickname": self.nickname,
            "emailHint": self.email_hint,
            "authSubject": self.auth_subject,
            "providerAccountID": self.provider_account_id,
            "codexHomePath": self.codex_home_path,
            "source": self.source.value,
            "createdAt": format_datetime(self.created_at),
            "updatedAt": format_datetime(self.updated_at),
            "lastAuthenticatedAt": format_datetime(self.last_authenticated_at),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "StoredAccount":
        return cls(
            id=UUID(str(payload["id"])),
            nickname=payload.get("nickname"),
            email_hint=payload.get("emailHint"),
            auth_subject=payload.get("authSubject"),
            provider_account_id=payload.get("providerAccountID"),
            codex_home_path=str(payload["codexHomePath"]),
            source=StoredAccountSource.from_raw(str(payload["source"])),
            created_at=parse_datetime(payload["createdAt"]) or utc_now(),
            updated_at=parse_datetime(payload["updatedAt"]) or utc_now(),
            last_authenticated_at=parse_datetime(payload.get("lastAuthenticatedAt")),
        )


@dataclass(slots=True)
class AccountRuntimeState:
    snapshot: "AccountUsageSnapshot | None" = None
    error_message: str | None = None
    is_loading: bool = False


@dataclass(slots=True)
class UsageWindowSnapshot:
    used_percent: float
    reset_at: datetime | None
    limit_window_seconds: int

    @property
    def remaining_percent(self) -> float:
        return max(0.0, 100.0 - self.used_percent)

    @property
    def display_name(self) -> str:
        if self.limit_window_seconds == 18_000:
            return "5 Hours"
        if self.limit_window_seconds == 604_800:
            return "7 Days"

        hours = self.limit_window_seconds / 3600
        if hours < 24:
            return f"{round(hours):.0f} Hours"
        days = hours / 24
        return f"{round(days):.0f} Days"

    @property
    def short_label(self) -> str:
        if self.limit_window_seconds == 18_000:
            return "5h"
        if self.limit_window_seconds == 604_800:
            return "7d"

        hours = self.limit_window_seconds / 3600
        if hours < 24:
            return f"{round(hours):.0f}h"
        days = hours / 24
        return f"{round(days):.0f}d"

    @property
    def reset_at_display(self) -> str | None:
        if self.reset_at is None:
            return None
        return self.reset_at.astimezone().strftime("%b %d, %Y %H:%M")

    @property
    def compact_reset_at_display(self) -> str | None:
        if self.reset_at is None:
            return None
        return self.reset_at.astimezone().strftime("%b %d %H:%M")

    def to_dict(self) -> dict[str, Any]:
        return {
            "usedPercent": self.used_percent,
            "resetAt": format_datetime(self.reset_at),
            "limitWindowSeconds": self.limit_window_seconds,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "UsageWindowSnapshot":
        return cls(
            used_percent=float(payload["usedPercent"]),
            reset_at=parse_datetime(payload.get("resetAt")),
            limit_window_seconds=int(payload["limitWindowSeconds"]),
        )


@dataclass(slots=True)
class CreditsBalanceSnapshot:
    has_credits: bool
    unlimited: bool
    balance: float | None

    @property
    def display_value(self) -> str:
        if self.unlimited:
            return "Unlimited"
        if self.balance is not None:
            return f"{self.balance:.2f}".rstrip("0").rstrip(".")
        if self.has_credits:
            return "Available"
        return "None"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hasCredits": self.has_credits,
            "unlimited": self.unlimited,
            "balance": self.balance,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CreditsBalanceSnapshot":
        balance = payload.get("balance")
        return cls(
            has_credits=bool(payload.get("hasCredits")),
            unlimited=bool(payload.get("unlimited")),
            balance=float(balance) if balance is not None else None,
        )


@dataclass(slots=True)
class AccountUsageSnapshot:
    email: str | None
    provider_account_id: str | None
    plan: str | None
    allowed: bool | None
    limit_reached: bool | None
    primary_window: UsageWindowSnapshot | None
    secondary_window: UsageWindowSnapshot | None
    credits: CreditsBalanceSnapshot | None
    updated_at: datetime

    @property
    def lowest_remaining_percent(self) -> float:
        if self.is_quota_blocked:
            return 0.0

        values = [
            candidate.remaining_percent
            for candidate in (self.secondary_window, self.primary_window)
            if candidate is not None
        ]
        return min(values) if values else 101.0

    @property
    def has_quota_windows(self) -> bool:
        return self.primary_window is not None or self.secondary_window is not None

    @property
    def is_quota_blocked(self) -> bool:
        return self.limit_reached is True or self.allowed is False

    @property
    def has_usable_quota_now(self) -> bool:
        if self.is_quota_blocked:
            return False

        values = [
            candidate.remaining_percent
            for candidate in (self.secondary_window, self.primary_window)
            if candidate is not None
        ]
        return bool(values) and any(value > 0.001 for value in values)

    @property
    def sort_priority(self) -> int:
        if self.has_usable_quota_now:
            return 0
        if self.next_reset_at is not None:
            return 1
        return 2

    @property
    def next_reset_at(self) -> datetime | None:
        values = [candidate.reset_at for candidate in (self.primary_window, self.secondary_window) if candidate and candidate.reset_at]
        return min(values) if values else None

    @property
    def plan_display_name(self) -> str:
        if not self.plan:
            return "Unknown"
        return " ".join(piece[:1].upper() + piece[1:].lower() for piece in self.plan.replace("_", " ").split())

    def to_dict(self) -> dict[str, Any]:
        return {
            "email": self.email,
            "providerAccountID": self.provider_account_id,
            "plan": self.plan,
            "allowed": self.allowed,
            "limitReached": self.limit_reached,
            "primaryWindow": self.primary_window.to_dict() if self.primary_window else None,
            "secondaryWindow": self.secondary_window.to_dict() if self.secondary_window else None,
            "credits": self.credits.to_dict() if self.credits else None,
            "updatedAt": format_datetime(self.updated_at),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AccountUsageSnapshot":
        primary = payload.get("primaryWindow")
        secondary = payload.get("secondaryWindow")
        credits = payload.get("credits")
        return cls(
            email=payload.get("email"),
            provider_account_id=payload.get("providerAccountID"),
            plan=payload.get("plan"),
            allowed=payload.get("allowed"),
            limit_reached=payload.get("limitReached"),
            primary_window=UsageWindowSnapshot.from_dict(primary) if primary else None,
            secondary_window=UsageWindowSnapshot.from_dict(secondary) if secondary else None,
            credits=CreditsBalanceSnapshot.from_dict(credits) if credits else None,
            updated_at=parse_datetime(payload["updatedAt"]) or utc_now(),
        )
