import hashlib
import hmac
import json


def compute_signature(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def signature_is_valid(secret: str, body: bytes, signature: str) -> bool:
    expected = compute_signature(secret, body)
    return hmac.compare_digest(expected, signature)


def normalize_event(*, source_key: str, event_type: str, entity_id: str, data: dict) -> dict:
    return {
        "source": source_key,
        "event_type": event_type,
        "entity_id": entity_id,
        "data": data,
    }


def serialize_payload(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
