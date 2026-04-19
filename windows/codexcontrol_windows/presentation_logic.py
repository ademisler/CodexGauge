from __future__ import annotations

from .codex_api import AuthBackedIdentity
from .models import AccountUsageSnapshot, StoredAccount, normalize_identifier


def account_sort_key(
    account: StoredAccount,
    snapshot: AccountUsageSnapshot | None,
) -> tuple[int, int, float, float, str]:
    priority = snapshot.sort_priority if snapshot else 2
    name = account.display_name.casefold()
    if snapshot is None:
        return priority, 1, 0.0, float("inf"), name

    reset_at = snapshot.next_reset_at.timestamp() if snapshot.next_reset_at else float("inf")
    if snapshot.has_usable_quota_now:
        return priority, 0, -snapshot.lowest_remaining_percent, reset_at, name
    return priority, 1, 0.0, reset_at, name


def is_active_account(account: StoredAccount, identity: AuthBackedIdentity | None) -> bool:
    if identity is None:
        return False

    account_subject = normalize_identifier(account.auth_subject)
    identity_subject = normalize_identifier(identity.auth_subject)
    if account_subject and identity_subject and account_subject == identity_subject:
        return True

    account_email = normalize_identifier(account.email_hint)
    identity_email = normalize_identifier(identity.email)
    if account_email and identity_email and account_email == identity_email:
        return True

    return False
