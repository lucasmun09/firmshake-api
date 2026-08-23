from flask import Blueprint, g, jsonify, request

from services.auth import AuthError, verify_firebase_token
from services.agreement_pipeline import (
    AgreementPipelineError,
    accept_agreement,
    cancel_agreement,
    create_deposit,
    decline_agreement,
    get_agreement,
    list_agreements,
    propose_agreement,
    start_en_route,
    update_agreement_location,
)
from services.stripe_deposits import StripeDepositError, is_stripe_configured, verify_stripe_webhook
from services.agreement_pipeline import confirm_deposit_from_stripe_webhook
from config import are_payments_enabled

agreements_bp = Blueprint("v1_agreements", __name__)
webhooks_bp = Blueprint("v1_webhooks", __name__)


def _pipeline_error_response(exc: AgreementPipelineError):
    return jsonify({"error": str(exc)}), exc.status_code


@agreements_bp.get("/<agreement_id>")
def get_agreement_route(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        agreement = get_agreement(actor_uid, agreement_id)
        return jsonify({"agreement": agreement}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to load FirmShake"}), 500


@agreements_bp.get("")
def list_agreements_route():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        role = request.args.get("role")
        listing_id = request.args.get("listingId")
        agreements = list_agreements(actor_uid, role=role, listing_id=listing_id)
        return jsonify({"agreements": agreements}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to list FirmShakes"}), 500


@agreements_bp.post("")
def post_agreement():
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        agreement = propose_agreement(actor_uid, payload)
        return jsonify({"agreement": agreement}), 201
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to propose FirmShake"}), 500


@agreements_bp.post("/<agreement_id>/accept")
def post_accept_agreement(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        agreement = accept_agreement(actor_uid, agreement_id)
        return jsonify({"agreement": agreement}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to accept FirmShake"}), 500


@agreements_bp.post("/<agreement_id>/decline")
def post_decline_agreement(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        agreement = decline_agreement(actor_uid, agreement_id)
        return jsonify({"agreement": agreement}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to decline FirmShake"}), 500


@agreements_bp.post("/<agreement_id>/cancel")
def post_cancel_agreement(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        agreement = cancel_agreement(actor_uid, agreement_id)
        return jsonify({"agreement": agreement}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to cancel FirmShake"}), 500


@agreements_bp.post("/<agreement_id>/deposit")
def post_deposit_agreement(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        payload = request.get_json(silent=True) or {}
        result = create_deposit(actor_uid, agreement_id, payload)
        return jsonify(result), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to process deposit"}), 500


@agreements_bp.post("/<agreement_id>/en-route")
def post_en_route_agreement(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        agreement = start_en_route(actor_uid, agreement_id)
        return jsonify({"agreement": agreement}), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to start en route"}), 500


@agreements_bp.post("/<agreement_id>/location")
def post_agreement_location(agreement_id: str):
    try:
        actor_uid = verify_firebase_token(request.headers.get("Authorization"))
        g.authenticated_uid = actor_uid
        body = request.get_json(silent=True) or {}
        lat = body.get("lat")
        lng = body.get("lng")
        if lat is None or lng is None:
            return jsonify({"error": "lat and lng are required"}), 400

        result = update_agreement_location(
            actor_uid,
            agreement_id,
            float(lat),
            float(lng),
        )
        return jsonify(result), 200
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except AgreementPipelineError as exc:
        return _pipeline_error_response(exc)
    except Exception:
        return jsonify({"error": "Failed to update meetup location"}), 500


@webhooks_bp.post("/stripe")
def post_stripe_webhook():
    if not are_payments_enabled():
        return jsonify({"received": True, "mode": "disabled"}), 200

    if not is_stripe_configured():
        return jsonify({"received": True, "mode": "stub"}), 200

    try:
        event = verify_stripe_webhook(
            request.get_data(),
            request.headers.get("Stripe-Signature"),
        )
    except StripeDepositError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    except Exception:
        return jsonify({"error": "Invalid Stripe webhook"}), 400

    event_type = event.get("type")
    if event_type == "checkout.session.completed":
        session = event.get("data", {}).get("object", {})
        metadata = session.get("metadata") or {}
        agreement_id = metadata.get("agreementId")
        buyer_id = metadata.get("buyerId")
        if agreement_id and buyer_id:
            try:
                confirm_deposit_from_stripe_webhook(agreement_id, buyer_id)
            except AgreementPipelineError:
                pass

    return jsonify({"received": True}), 200
