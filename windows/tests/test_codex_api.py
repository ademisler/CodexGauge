from __future__ import annotations

import base64
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from codexcontrol_windows.codex_api import (
    AuthCredentials,
    _fetch_snapshot,
    _identity_from_credentials,
    _normalize_window_roles,
    _parse_chatgpt_base_url,
    fetch_snapshot,
)
from codexcontrol_windows.models import AccountUsageSnapshot, StoredAccount, StoredAccountSource, UsageWindowSnapshot


class CodexApiTests(unittest.TestCase):
    def test_identity_from_credentials_uses_id_token_payload(self) -> None:
        payload = {
            "email": "user@example.com",
            "sub": "auth0|user",
            "https://api.openai.com/auth": {
                "chatgpt_plan_type": "team",
                "chatgpt_account_id": "provider-1",
            },
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        credentials = AuthCredentials(
            access_token="token",
            refresh_token="",
            id_token=f"header.{encoded}.signature",
            account_id="provider-1",
            last_refresh=datetime(2026, 4, 18, tzinfo=timezone.utc),
        )

        identity = _identity_from_credentials(credentials)

        self.assertEqual(identity.email, "user@example.com")
        self.assertEqual(identity.auth_subject, "auth0|user")
        self.assertEqual(identity.plan, "team")
        self.assertEqual(identity.provider_account_id, "provider-1")

    def test_parse_chatgpt_base_url(self) -> None:
        contents = """
        # comment
        chatgpt_base_url = "https://example.com/custom"
        """

        self.assertEqual(_parse_chatgpt_base_url(contents), "https://example.com/custom")

    def test_normalize_window_roles_swaps_weekly_into_secondary_slot(self) -> None:
        now = datetime(2026, 4, 18, tzinfo=timezone.utc)
        weekly = UsageWindowSnapshot(used_percent=12.0, reset_at=now, limit_window_seconds=604_800)
        session = UsageWindowSnapshot(used_percent=45.0, reset_at=now, limit_window_seconds=18_000)

        primary, secondary = _normalize_window_roles(weekly, session)

        self.assertEqual(primary.limit_window_seconds, 18_000)
        self.assertEqual(secondary.limit_window_seconds, 604_800)

    def test_fetch_snapshot_can_skip_verification_for_bulk_refresh(self) -> None:
        now = datetime(2026, 4, 18, tzinfo=timezone.utc)
        account = StoredAccount(
            id=uuid4(),
            nickname=None,
            email_hint="user@example.com",
            auth_subject="auth0|user",
            provider_account_id="provider-1",
            codex_home_path="C:/temp/account",
            source=StoredAccountSource.MANAGED_BY_APP,
            created_at=now,
            updated_at=now,
            last_authenticated_at=now,
        )
        credentials = AuthCredentials(
            access_token="token",
            refresh_token="",
            id_token=None,
            account_id="provider-1",
            last_refresh=now,
        )
        snapshot = AccountUsageSnapshot(
            email="user@example.com",
            provider_account_id="provider-1",
            plan="team",
            allowed=True,
            limit_reached=False,
            primary_window=UsageWindowSnapshot(used_percent=30.0, reset_at=now, limit_window_seconds=18_000),
            secondary_window=None,
            credits=None,
            updated_at=now,
        )

        with (
            patch("codexcontrol_windows.codex_api._load_credentials", return_value=credentials),
            patch("codexcontrol_windows.codex_api._fetch_snapshot", return_value=snapshot) as fast_fetch,
            patch("codexcontrol_windows.codex_api._fetch_verified_snapshot", return_value=snapshot) as verified_fetch,
        ):
            result = fetch_snapshot(account, verify_live_data=False)

        self.assertIs(result, snapshot)
        fast_fetch.assert_called_once()
        verified_fetch.assert_not_called()

    def test_raw_fetch_snapshot_uses_credentials_identity_without_reloading_auth(self) -> None:
        now = datetime(2026, 4, 18, tzinfo=timezone.utc)
        payload = {
            "email": "user@example.com",
            "sub": "auth0|user",
            "https://api.openai.com/auth": {
                "chatgpt_plan_type": "team",
                "chatgpt_account_id": "provider-1",
            },
        }
        encoded = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8").rstrip("=")
        credentials = AuthCredentials(
            access_token="token",
            refresh_token="",
            id_token=f"header.{encoded}.signature",
            account_id="provider-1",
            last_refresh=now,
        )
        api_payload = {
            "plan_type": "team",
            "rate_limit": {
                "allowed": True,
                "limit_reached": False,
                "primary_window": {
                    "used_percent": 30.0,
                    "reset_at": now.timestamp(),
                    "limit_window_seconds": 18_000,
                },
            },
        }

        with (
            patch("codexcontrol_windows.codex_api._fetch_usage", return_value=api_payload),
            patch("codexcontrol_windows.codex_api.load_identity", side_effect=AssertionError("should not reload auth")),
        ):
            snapshot = _fetch_snapshot("C:/temp/account", credentials, "fallback@example.com")

        self.assertEqual(snapshot.email, "user@example.com")
        self.assertEqual(snapshot.provider_account_id, "provider-1")
        self.assertEqual(snapshot.plan, "team")


if __name__ == "__main__":
    unittest.main()
