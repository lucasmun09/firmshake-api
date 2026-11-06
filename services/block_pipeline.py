"""Block/unblock users mirroring firmshake client blocks.ts."""

import logging

from google.cloud import firestore

from services.firebase_app import get_db

logger = logging.getLogger("firmshake.block_pipeline")

ACTIVE_AGREEMENT_STATUSES = {"proposed", "accepted", "deposit_paid", "en_route"}


class BlockPipelineError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _serialize_blocked_entry(blocked_user_id: str, data: dict) -> dict:
    blocked_at = data.get("blockedAt")
    blocked_at_ms = None
    if blocked_at is not None and hasattr(blocked_at, "timestamp"):
        blocked_at_ms = int(blocked_at.timestamp() * 1000)
    return {
        "blockedUserId": blocked_user_id,
        "blockedAt": blocked_at_ms,
    }


def list_blocked_users(blocker_id: str) -> list[dict]:
    db = get_db()
    snapshot = db.collection("users").document(blocker_id).collection("blockedUsers").stream()
    return [
        _serialize_blocked_entry(doc.id, doc.to_dict() or {})
        for doc in snapshot
    ]


def _cancel_active_agreements_between(db, uid_a: str, uid_b: str, cancelled_by: str) -> int:
    """Cancel active agreements between two users using agreement_pipeline when available."""
    try:
        from services.agreement_pipeline import cancel_active_agreement_on_block
    except ImportError:
        cancel_active_agreement_on_block = None

    cancelled = 0
    seen: set[str] = set()

    for field, other in (("buyerId", uid_b), ("sellerId", uid_b)):
        query = (
            db.collection("agreements")
            .where(field, "==", uid_a)
            .where("status", "in", list(ACTIVE_AGREEMENT_STATUSES))
        )
        for doc in query.stream():
            if doc.id in seen:
                continue
            agreement = doc.to_dict() or {}
            other_party = agreement.get("sellerId") if field == "buyerId" else agreement.get("buyerId")
            if other_party != other:
                continue
            seen.add(doc.id)

            if cancel_active_agreement_on_block is not None:
                try:
                    result = cancel_active_agreement_on_block(cancelled_by, doc.id)
                    if result is not None:
                        cancelled += 1
                    continue
                except Exception as exc:
                    logger.warning(
                        "agreement_pipeline cancel on block failed; falling back",
                        extra={"agreement_id": doc.id, "error": str(exc)},
                    )

            doc.reference.set(
                {
                    "status": "cancelled",
                    "cancelledBy": cancelled_by,
                    "updatedAt": firestore.SERVER_TIMESTAMP,
                },
                merge=True,
            )
            cancelled += 1

    return cancelled


def block_user(blocker_id: str, blocked_user_id: str) -> dict:
    if blocker_id == blocked_user_id:
        raise BlockPipelineError("You cannot block yourself")

    db = get_db()
    blocked_profile = db.collection("users").document(blocked_user_id).get()
    if not blocked_profile.exists:
        raise BlockPipelineError("User not found", 404)

    block_ref = (
        db.collection("users")
        .document(blocker_id)
        .collection("blockedUsers")
        .document(blocked_user_id)
    )
    block_ref.set(
        {
            "blockedUserId": blocked_user_id,
            "blockedAt": firestore.SERVER_TIMESTAMP,
        }
    )

    try:
        count = _cancel_active_agreements_between(db, blocker_id, blocked_user_id, blocker_id)
        if count:
            logger.info(
                "cancelled agreements on block",
                extra={
                    "blocker_id": blocker_id,
                    "blocked_user_id": blocked_user_id,
                    "count": count,
                },
            )
    except Exception as exc:
        logger.warning(
            "agreement cancellation on block failed",
            extra={
                "blocker_id": blocker_id,
                "blocked_user_id": blocked_user_id,
                "error": str(exc),
            },
        )

    snapshot = block_ref.get()
    return _serialize_blocked_entry(blocked_user_id, snapshot.to_dict() or {})


def unblock_user(blocker_id: str, blocked_user_id: str) -> None:
    if blocker_id == blocked_user_id:
        return

    db = get_db()
    block_ref = (
        db.collection("users")
        .document(blocker_id)
        .collection("blockedUsers")
        .document(blocked_user_id)
    )
    if block_ref.get().exists:
        block_ref.delete()
