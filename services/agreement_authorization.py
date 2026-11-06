"""Authorization and state-transition rules for FirmShake agreements."""

from services.firebase_app import get_db
from services.message_authorization import is_user_blocked

MIN_DEPOSIT_AMOUNT = 10

ACTIVE_STATUSES = frozenset({"proposed", "accepted", "deposit_paid", "en_route"})
TERMINAL_STATUSES = frozenset(
    {"cancelled", "completed", "no_show_buyer", "no_show_seller"}
)


class AgreementAuthorizationError(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def assert_is_participant(actor_uid: str, agreement: dict) -> None:
    buyer_id = str(agreement.get("buyerId", ""))
    seller_id = str(agreement.get("sellerId", ""))
    if actor_uid not in {buyer_id, seller_id}:
        raise AgreementAuthorizationError("You are not part of this FirmShake", 403)


def assert_not_blocked(buyer_id: str, seller_id: str) -> None:
    if is_user_blocked(seller_id, buyer_id):
        raise AgreementAuthorizationError(
            "This seller is not accepting FirmShake requests from you",
            403,
        )
    if is_user_blocked(buyer_id, seller_id):
        raise AgreementAuthorizationError(
            "This buyer is not available for FirmShake requests",
            403,
        )


def assert_can_propose(actor_uid: str, listing: dict, payload: dict) -> None:
    seller_id = str(listing.get("sellerId", ""))
    if actor_uid != str(payload.get("buyerId", "")):
        raise AgreementAuthorizationError("Only the buyer can propose a FirmShake", 403)
    if seller_id != str(payload.get("sellerId", "")):
        raise AgreementAuthorizationError("Seller does not match listing", 400)
    if actor_uid == seller_id:
        raise AgreementAuthorizationError("You cannot propose a FirmShake on your own listing", 403)

    deposit = float(payload.get("depositAmount", 0))
    if deposit < MIN_DEPOSIT_AMOUNT:
        raise AgreementAuthorizationError(
            f"Deposit must be at least ${MIN_DEPOSIT_AMOUNT}",
            400,
        )

    assert_not_blocked(actor_uid, seller_id)


def _has_active_agreement(db, listing_id: str, buyer_id: str) -> bool:
    snapshot = (
        db.collection("agreements")
        .where("listingId", "==", listing_id)
        .where("buyerId", "==", buyer_id)
        .stream()
    )
    for doc in snapshot:
        status = (doc.to_dict() or {}).get("status", "")
        if status not in TERMINAL_STATUSES:
            return True
    return False


def assert_no_active_agreement(db, listing_id: str, buyer_id: str) -> None:
    if _has_active_agreement(db, listing_id, buyer_id):
        raise AgreementAuthorizationError(
            "You already have an active FirmShake request for this listing",
            400,
        )


def assert_can_accept(actor_uid: str, agreement: dict) -> None:
    assert_is_participant(actor_uid, agreement)
    seller_id = str(agreement.get("sellerId", ""))
    if actor_uid != seller_id:
        raise AgreementAuthorizationError("Only the seller can accept a FirmShake", 403)
    if agreement.get("status") != "proposed":
        raise AgreementAuthorizationError("Only pending FirmShake requests can be accepted", 400)


def assert_can_decline(actor_uid: str, agreement: dict) -> None:
    assert_is_participant(actor_uid, agreement)
    seller_id = str(agreement.get("sellerId", ""))
    if actor_uid != seller_id:
        raise AgreementAuthorizationError("Only the seller can decline a FirmShake", 403)
    if agreement.get("status") != "proposed":
        raise AgreementAuthorizationError("Only pending FirmShake requests can be declined", 400)


def assert_can_buyer_cancel_proposed(actor_uid: str, agreement: dict) -> None:
    assert_is_participant(actor_uid, agreement)
    buyer_id = str(agreement.get("buyerId", ""))
    if actor_uid != buyer_id:
        raise AgreementAuthorizationError("You can only cancel your own FirmShake request", 403)
    if agreement.get("status") != "proposed":
        raise AgreementAuthorizationError("Only pending FirmShake requests can be cancelled", 400)


def assert_can_cancel_active(actor_uid: str, agreement: dict) -> None:
    assert_is_participant(actor_uid, agreement)
    status = agreement.get("status", "")
    if status == "proposed":
        raise AgreementAuthorizationError(
            "Use buyer cancel or seller decline for pending requests",
            400,
        )
    if status not in {"accepted", "deposit_paid", "en_route"}:
        raise AgreementAuthorizationError("This FirmShake cannot be cancelled", 400)


def assert_can_confirm_deposit(actor_uid: str, agreement: dict) -> None:
    assert_is_participant(actor_uid, agreement)
    buyer_id = str(agreement.get("buyerId", ""))
    if actor_uid != buyer_id:
        raise AgreementAuthorizationError("Only the buyer can pay the deposit", 403)
    if agreement.get("status") != "accepted":
        raise AgreementAuthorizationError(
            "Deposit can only be paid after the seller accepts",
            400,
        )


def assert_can_start_en_route(actor_uid: str, agreement: dict) -> None:
    assert_is_participant(actor_uid, agreement)
    if agreement.get("status") != "deposit_paid":
        raise AgreementAuthorizationError(
            "You can only go en route after the deposit is paid",
            400,
        )


def get_block_cancel_action(agreement: dict, user_id: str) -> str | None:
    """Return cancel action for block side-effect integration (Phase 4 block BFF)."""
    status = agreement.get("status", "")
    if status not in ACTIVE_STATUSES:
        return None

    buyer_id = str(agreement.get("buyerId", ""))
    seller_id = str(agreement.get("sellerId", ""))

    if status == "proposed":
        if user_id == buyer_id:
            return "buyer-cancel-proposed"
        if user_id == seller_id:
            return "seller-decline-proposed"
        return None

    if user_id in {buyer_id, seller_id}:
        return "direct-cancel"
    return None
