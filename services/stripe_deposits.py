"""Stripe checkout for FirmShake deposits (optional — mock path when not configured)."""

import os
from typing import Any

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()


class StripeDepositError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def is_stripe_configured() -> bool:
    return bool(STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET)


def create_deposit_checkout_session(
    *,
    agreement_id: str,
    buyer_id: str,
    deposit_amount: float,
    listing_id: str,
    success_url: str,
    cancel_url: str,
) -> dict[str, Any]:
    if not is_stripe_configured():
        raise StripeDepositError("Stripe is not configured", 503)

    try:
        import stripe
    except ImportError as exc:
        raise StripeDepositError("Stripe SDK is not installed", 503) from exc

    stripe.api_key = STRIPE_SECRET_KEY

    amount_cents = int(round(deposit_amount * 100))
    if amount_cents < 1000:
        raise StripeDepositError("Deposit must be at least $10", 400)

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "FirmShake meetup deposit",
                        "description": f"Deposit for listing {listing_id}",
                    },
                    "unit_amount": amount_cents,
                },
                "quantity": 1,
            }
        ],
        metadata={
            "agreementId": agreement_id,
            "buyerId": buyer_id,
            "listingId": listing_id,
        },
        success_url=success_url,
        cancel_url=cancel_url,
    )

    return {
        "mode": "stripe",
        "checkoutSessionId": session.id,
        "checkoutUrl": session.url,
    }


def verify_stripe_webhook(payload: bytes, sig_header: str | None) -> dict[str, Any]:
    if not is_stripe_configured():
        raise StripeDepositError("Stripe is not configured", 503)

    if not sig_header:
        raise StripeDepositError("Missing Stripe signature", 400)

    try:
        import stripe
    except ImportError as exc:
        raise StripeDepositError("Stripe SDK is not installed", 503) from exc

    stripe.api_key = STRIPE_SECRET_KEY
    event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    return event
