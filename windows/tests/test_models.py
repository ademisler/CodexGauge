from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from codexcontrol_windows.models import (
    AccountUsageSnapshot,
    StoredAccount,
    StoredAccountSource,
    UsageWindowSnapshot,
)


class StoredAccountTests(unittest.TestCase):
    def test_merge_prefers_managed_account_identity(self) -> None:
        created_at = datetime(2026, 4, 18, tzinfo=timezone.utc)
        original = StoredAccount(
            id=uuid4(),
            nickname=None,
            email_hint="legacy@example.com",
            auth_subject=None,
            provider_account_id=None,
            codex_home_path="C:/temp/a",
            source=StoredAccountSource.AMBIENT,
            created_at=created_at,
            updated_at=created_at,
        )
        candidate = StoredAccount(
            id=uuid4(),
            nickname=None,
            email_hint="team@example.com",
            auth_subject="auth0|abc",
            provider_account_id="account-1",
            codex_home_path="C:/temp/b",
            source=StoredAccountSource.MANAGED_BY_APP,
            created_at=created_at,
            updated_at=created_at + timedelta(minutes=5),
            last_authenticated_at=created_at + timedelta(minutes=5),
        )

        original.merge_from(candidate)

        self.assertEqual(original.email_hint, "team@example.com")
        self.assertEqual(original.auth_subject, "auth0|abc")
        self.assertEqual(original.provider_account_id, "account-1")
        self.assertEqual(original.codex_home_path, "C:/temp/b")


class SnapshotTests(unittest.TestCase):
    def test_snapshot_prefers_lowest_remaining_window(self) -> None:
        now = datetime(2026, 4, 18, tzinfo=timezone.utc)
        snapshot = AccountUsageSnapshot(
            email="user@example.com",
            provider_account_id="account-1",
            plan="team",
            allowed=True,
            limit_reached=False,
            primary_window=UsageWindowSnapshot(used_percent=35.0, reset_at=now, limit_window_seconds=18_000),
            secondary_window=UsageWindowSnapshot(used_percent=90.0, reset_at=now, limit_window_seconds=604_800),
            credits=None,
            updated_at=now,
        )

        self.assertTrue(snapshot.has_usable_quota_now)
        self.assertEqual(snapshot.lowest_remaining_percent, 10.0)
        self.assertEqual(snapshot.plan_display_name, "Team")


if __name__ == "__main__":
    unittest.main()
