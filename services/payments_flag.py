"""Meetup deposit payments flag (API).

This phase ships without a payment processor. Prod must keep PAYMENTS_ENABLED=false.
Devo may leave the flag enabled so create_deposit can use the **mock** path only
(no Stripe keys required / configured). Never add live Stripe keys.

Alias STRIPE_PAYMENTS_ENABLED wins when set. Default True for deovo/local mock.
"""

from __future__ import annotations

import os


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def are_payments_enabled() -> bool:
    """Whether deposit endpoints accept requests.

    When true without Stripe keys, agreement_pipeline uses mock deposit confirmation.
    When false, deposit creation returns 503.
    Alias: STRIPE_PAYMENTS_ENABLED wins when set.
    """
    if os.getenv("STRIPE_PAYMENTS_ENABLED", "").strip():
        return _parse_bool_env("STRIPE_PAYMENTS_ENABLED", True)
    return _parse_bool_env("PAYMENTS_ENABLED", True)


PAYMENTS_DISABLED_MESSAGE = "Deposit payment is unavailable on this environment"
