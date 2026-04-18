from __future__ import annotations

import unittest
from datetime import datetime, timezone

from codexcontrol_windows.codex_api import _normalize_window_roles, _parse_chatgpt_base_url
from codexcontrol_windows.models import UsageWindowSnapshot


class CodexApiTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
