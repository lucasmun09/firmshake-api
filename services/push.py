from firebase_admin import messaging

from services.firebase_app import get_db


def _collect_user_tokens(user_id: str) -> list[tuple[str, str]]:
    db = get_db()
    tokens_ref = (
        db.collection("users").document(user_id).collection("fcmTokens")
    )
    return [
        (doc.id, str(doc.to_dict().get("token") or ""))
        for doc in tokens_ref.stream()
        if doc.to_dict().get("token")
    ]


def _remove_token(user_id: str, token_doc_id: str) -> None:
    db = get_db()
    db.collection("users").document(user_id).collection("fcmTokens").document(
        token_doc_id
    ).delete()


def send_push_to_user(
    user_id: str,
    title: str,
    body: str,
    data: dict[str, str] | None = None,
) -> int:
    token_entries = _collect_user_tokens(user_id)
    if not token_entries:
        return 0

    tokens = [token for _, token in token_entries]
    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data or {},
        tokens=tokens,
    )

    response = messaging.send_each_for_multicast(message)
    sent = 0

    for index, send_response in enumerate(response.responses):
        token_doc_id, _token = token_entries[index]
        if send_response.success:
            sent += 1
            continue

        error = send_response.exception
        if isinstance(error, messaging.UnregisteredError):
            _remove_token(user_id, token_doc_id)

    return sent
