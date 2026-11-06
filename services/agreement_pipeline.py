"""FirmShake agreement mutations with notifications (mirrors client agreements.ts)."""

from datetime import datetime, timezone

from google.cloud import firestore

from services.agreement_authorization import (
    AgreementAuthorizationError,
    TERMINAL_STATUSES,
    assert_can_accept,
    assert_can_buyer_cancel_proposed,
    assert_can_cancel_active,
    assert_can_confirm_deposit,
    assert_can_decline,
    assert_can_propose,
    assert_can_start_en_route,
    assert_is_participant,
    assert_no_active_agreement,
    assert_not_blocked,
    get_block_cancel_action,
)
from services.firebase_app import get_db
from services.meetups import MeetupError, update_meetup_location
from services.push import send_push_to_user
from services.stripe_deposits import (
    StripeDepositError,
    create_deposit_checkout_session,
    is_stripe_configured,
)
from services.payments_flag import PAYMENTS_DISABLED_MESSAGE, are_payments_enabled


class AgreementPipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _auth_error(exc: AgreementAuthorizationError) -> AgreementPipelineError:
    return AgreementPipelineError(str(exc), exc.status_code)


def _parse_timestamp(value) -> int | None:
    if value is None:
        return None
    if hasattr(value, "timestamp"):
        return int(value.timestamp() * 1000)
    if isinstance(value, datetime):
        return int(value.timestamp() * 1000)
    return None


def _serialize_agreement(agreement_id: str, data: dict) -> dict:
    return {
        "id": agreement_id,
        "listingId": data.get("listingId", ""),
        "buyerId": data.get("buyerId", ""),
        "buyerName": data.get("buyerName", "Buyer"),
        "sellerId": data.get("sellerId", ""),
        "price": float(data.get("price", 0)),
        "meetupLat": float(data.get("meetupLat", 0)),
        "meetupLng": float(data.get("meetupLng", 0)),
        "meetupAddress": data.get("meetupAddress"),
        "meetupAt": _parse_timestamp(data.get("meetupAt")),
        "depositAmount": float(data.get("depositAmount", 0)),
        "depositPaidAt": _parse_timestamp(data.get("depositPaidAt")),
        "status": data.get("status", "proposed"),
        "cancelledBy": data.get("cancelledBy"),
        "buyerEtaMinutes": data.get("buyerEtaMinutes"),
        "buyerProgressPercent": data.get("buyerProgressPercent"),
        "sellerEtaMinutes": data.get("sellerEtaMinutes"),
        "sellerProgressPercent": data.get("sellerProgressPercent"),
    }


def _get_agreement_or_raise(db, agreement_id: str) -> tuple[dict, object]:
    doc_ref = db.collection("agreements").document(agreement_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        raise AgreementPipelineError("FirmShake not found", 404)
    return snapshot.to_dict() or {}, doc_ref


def _create_meetup_notification(
    db,
    *,
    recipient_id: str,
    actor_id: str,
    title: str,
    body: str,
    listing_id: str,
) -> None:
    if recipient_id == actor_id:
        return

    notification_ref = (
        db.collection("users").document(recipient_id).collection("notifications").document()
    )
    notification_ref.set(
        {
            "recipientId": recipient_id,
            "actorId": actor_id,
            "type": "meetup",
            "title": title,
            "body": body,
            "listingId": listing_id,
            "read": False,
            "createdAt": firestore.SERVER_TIMESTAMP,
        }
    )

    send_push_to_user(
        recipient_id,
        title,
        body,
        {
            "type": "meetup",
            "actorId": actor_id,
            "listingId": listing_id,
        },
    )


def _parse_meetup_at(value) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AgreementPipelineError("Invalid meetupAt", 400) from exc
    raise AgreementPipelineError("meetupAt is required", 400)


def propose_agreement(actor_uid: str, payload: dict) -> dict:
    listing_id = str(payload.get("listingId", "")).strip()
    if not listing_id:
        raise AgreementPipelineError("listingId is required", 400)

    buyer_name = str(payload.get("buyerName", "")).strip()
    if not buyer_name:
        raise AgreementPipelineError("buyerName is required", 400)

    db = get_db()
    listing_snapshot = db.collection("listings").document(listing_id).get()
    if not listing_snapshot.exists:
        raise AgreementPipelineError("Listing not found", 404)

    listing = listing_snapshot.to_dict() or {}

    normalized = {
        "listingId": listing_id,
        "buyerId": str(payload.get("buyerId", actor_uid)),
        "buyerName": buyer_name,
        "sellerId": str(payload.get("sellerId", listing.get("sellerId", ""))),
        "price": float(payload.get("price", listing.get("price", 0))),
        "meetupLat": float(payload.get("meetupLat", 0)),
        "meetupLng": float(payload.get("meetupLng", 0)),
        "meetupAddress": payload.get("meetupAddress"),
        "meetupAt": _parse_meetup_at(payload.get("meetupAt")),
        "depositAmount": float(payload.get("depositAmount", 10)),
    }

    try:
        assert_can_propose(actor_uid, listing, normalized)
        assert_no_active_agreement(db, listing_id, normalized["buyerId"])
    except AgreementAuthorizationError as exc:
        raise _auth_error(exc) from exc

    doc_ref = db.collection("agreements").document()
    doc_ref.set(
        {
            **normalized,
            "meetupAddress": normalized.get("meetupAddress"),
            "meetupAt": normalized["meetupAt"],
            "status": "proposed",
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )

    agreement_data = {**normalized, "status": "proposed"}
    result = _serialize_agreement(doc_ref.id, agreement_data)

    try:
        _create_meetup_notification(
            db,
            recipient_id=normalized["sellerId"],
            actor_id=normalized["buyerId"],
            title=f"{buyer_name} requested a FirmShake",
            body=(
                f"Review the FirmShake for ${normalized['price']:.0f} "
                f"with a ${normalized['depositAmount']:.0f} deposit."
            ),
            listing_id=listing_id,
        )
    except Exception:
        pass

    return result


def get_agreement(actor_uid: str, agreement_id: str) -> dict:
    db = get_db()
    agreement, _doc_ref = _get_agreement_or_raise(db, agreement_id)
    try:
        assert_is_participant(actor_uid, agreement)
    except AgreementAuthorizationError as exc:
        raise _auth_error(exc) from exc
    return _serialize_agreement(agreement_id, agreement)


def list_agreements(
    actor_uid: str,
    *,
    role: str | None = None,
    listing_id: str | None = None,
) -> list[dict]:
    db = get_db()
    role_normalized = (role or "").strip().lower()

    if role_normalized == "buyer":
        query = db.collection("agreements").where("buyerId", "==", actor_uid)
    elif role_normalized == "seller":
        query = db.collection("agreements").where("sellerId", "==", actor_uid)
    else:
        raise AgreementPipelineError("role must be buyer or seller", 400)

    if listing_id:
        query = query.where("listingId", "==", listing_id.strip())

    agreements = []
    for doc in query.stream():
        data = doc.to_dict() or {}
        agreements.append(_serialize_agreement(doc.id, data))

    agreements.sort(key=lambda item: item.get("meetupAt") or 0, reverse=True)
    return agreements


def accept_agreement(actor_uid: str, agreement_id: str) -> dict:
    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)

    try:
        assert_can_accept(actor_uid, agreement)
    except AgreementAuthorizationError as exc:
        raise _auth_error(exc) from exc

    doc_ref.set(
        {
            "status": "accepted",
            "acceptedAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    deposit_amount = float(agreement.get("depositAmount", 0))
    try:
        _create_meetup_notification(
            db,
            recipient_id=str(agreement.get("buyerId", "")),
            actor_id=actor_uid,
            title="FirmShake accepted",
            body=f"Pay the ${deposit_amount:.0f} deposit to lock in your meetup.",
            listing_id=str(agreement.get("listingId", "")),
        )
    except Exception:
        pass

    updated = {**agreement, "status": "accepted"}
    return _serialize_agreement(agreement_id, updated)


def decline_agreement(actor_uid: str, agreement_id: str) -> dict:
    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)

    try:
        assert_can_decline(actor_uid, agreement)
    except AgreementAuthorizationError as exc:
        raise _auth_error(exc) from exc

    doc_ref.set(
        {
            "status": "cancelled",
            "cancelledBy": actor_uid,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    updated = {**agreement, "status": "cancelled", "cancelledBy": actor_uid}
    return _serialize_agreement(agreement_id, updated)


def cancel_agreement(actor_uid: str, agreement_id: str) -> dict:
    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)
    status = agreement.get("status", "")

    if status == "proposed":
        try:
            assert_can_buyer_cancel_proposed(actor_uid, agreement)
        except AgreementAuthorizationError as exc:
            raise _auth_error(exc) from exc
    else:
        try:
            assert_can_cancel_active(actor_uid, agreement)
        except AgreementAuthorizationError as exc:
            raise _auth_error(exc) from exc

    doc_ref.set(
        {
            "status": "cancelled",
            "cancelledBy": actor_uid,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    updated = {**agreement, "status": "cancelled", "cancelledBy": actor_uid}
    return _serialize_agreement(agreement_id, updated)


def cancel_active_agreement_on_block(actor_uid: str, agreement_id: str) -> dict | None:
    """Integration point for Phase 4 block BFF — cancel active agreement when user is blocked."""
    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)
    action = get_block_cancel_action(agreement, actor_uid)
    if not action:
        return None

    if action == "buyer-cancel-proposed":
        return cancel_agreement(actor_uid, agreement_id)
    if action == "seller-decline-proposed":
        return decline_agreement(actor_uid, agreement_id)

    doc_ref.set(
        {
            "status": "cancelled",
            "cancelledBy": actor_uid,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    updated = {**agreement, "status": "cancelled", "cancelledBy": actor_uid}
    return _serialize_agreement(agreement_id, updated)


def create_deposit(actor_uid: str, agreement_id: str, payload: dict | None = None) -> dict:
    if not are_payments_enabled():
        raise AgreementPipelineError(
            PAYMENTS_DISABLED_MESSAGE,
            503,
        )

    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)

    try:
        assert_can_confirm_deposit(actor_uid, agreement)
    except AgreementAuthorizationError as exc:
        raise _auth_error(exc) from exc

    payload = payload or {}
    deposit_amount = float(agreement.get("depositAmount", 0))

    if is_stripe_configured():
        success_url = str(payload.get("successUrl", "")).strip()
        cancel_url = str(payload.get("cancelUrl", "")).strip()
        if not success_url or not cancel_url:
            raise AgreementPipelineError("successUrl and cancelUrl are required for Stripe checkout", 400)

        try:
            session = create_deposit_checkout_session(
                agreement_id=agreement_id,
                buyer_id=actor_uid,
                deposit_amount=deposit_amount,
                listing_id=str(agreement.get("listingId", "")),
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except StripeDepositError as exc:
            raise AgreementPipelineError(str(exc), exc.status_code) from exc

        return {
            "agreement": _serialize_agreement(agreement_id, agreement),
            **session,
        }

    doc_ref.set(
        {
            "status": "deposit_paid",
            "depositPaidAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    buyer_name = str(agreement.get("buyerName", "Buyer"))
    try:
        _create_meetup_notification(
            db,
            recipient_id=str(agreement.get("sellerId", "")),
            actor_id=actor_uid,
            title="Deposit received",
            body=(
                f"{buyer_name} paid the meetup deposit. "
                "You can head to the meetup when ready."
            ),
            listing_id=str(agreement.get("listingId", "")),
        )
    except Exception:
        pass

    updated = {**agreement, "status": "deposit_paid"}
    return {
        "mode": "mock",
        "agreement": _serialize_agreement(agreement_id, updated),
    }


def confirm_deposit_from_stripe_webhook(agreement_id: str, buyer_id: str) -> dict:
    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)

    if str(agreement.get("buyerId", "")) != buyer_id:
        raise AgreementPipelineError("Stripe buyer does not match agreement", 400)

    if agreement.get("status") != "accepted":
        raise AgreementPipelineError("Agreement is not awaiting deposit", 400)

    doc_ref.set(
        {
            "status": "deposit_paid",
            "depositPaidAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    buyer_name = str(agreement.get("buyerName", "Buyer"))
    try:
        _create_meetup_notification(
            db,
            recipient_id=str(agreement.get("sellerId", "")),
            actor_id=buyer_id,
            title="Deposit received",
            body=(
                f"{buyer_name} paid the meetup deposit. "
                "You can head to the meetup when ready."
            ),
            listing_id=str(agreement.get("listingId", "")),
        )
    except Exception:
        pass

    updated = {**agreement, "status": "deposit_paid"}
    return _serialize_agreement(agreement_id, updated)


def start_en_route(actor_uid: str, agreement_id: str) -> dict:
    db = get_db()
    agreement, doc_ref = _get_agreement_or_raise(db, agreement_id)

    try:
        assert_can_start_en_route(actor_uid, agreement)
    except AgreementAuthorizationError as exc:
        raise _auth_error(exc) from exc

    doc_ref.set(
        {
            "status": "en_route",
            "enRouteAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    updated = {**agreement, "status": "en_route"}
    return _serialize_agreement(agreement_id, updated)


def update_agreement_location(
    actor_uid: str,
    agreement_id: str,
    lat: float,
    lng: float,
) -> dict:
    try:
        return update_meetup_location(agreement_id, actor_uid, lat, lng)
    except MeetupError as exc:
        raise AgreementPipelineError(str(exc), exc.status_code) from exc
