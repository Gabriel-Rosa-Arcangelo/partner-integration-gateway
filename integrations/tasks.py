import requests
from celery import shared_task

from .models import DeliveryAttempt
from .services import compute_signature, serialize_payload

MAX_ATTEMPTS = 3


@shared_task
def deliver_webhook(delivery_attempt_id: int):
    attempt = DeliveryAttempt.objects.select_related("event", "subscription").get(pk=delivery_attempt_id)
    if attempt.status in [DeliveryAttempt.Status.DELIVERED, DeliveryAttempt.Status.DEAD_LETTER]:
        return

    body = serialize_payload(attempt.event.normalized_payload)
    signature = compute_signature(attempt.subscription.signing_secret, body)
    attempt.attempt_count += 1

    try:
        response = requests.post(
            attempt.subscription.url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Event-ID": str(attempt.event.id),
                "X-Signature": signature,
            },
            timeout=10,
        )
        attempt.response_code = response.status_code
        if 200 <= response.status_code < 300:
            attempt.status = DeliveryAttempt.Status.DELIVERED
            attempt.last_error = ""
        else:
            attempt.status = (
                DeliveryAttempt.Status.DEAD_LETTER
                if attempt.attempt_count >= MAX_ATTEMPTS
                else DeliveryAttempt.Status.FAILED
            )
            attempt.last_error = f"Unexpected response status: {response.status_code}"
    except requests.RequestException as exc:
        attempt.status = (
            DeliveryAttempt.Status.DEAD_LETTER
            if attempt.attempt_count >= MAX_ATTEMPTS
            else DeliveryAttempt.Status.FAILED
        )
        attempt.last_error = str(exc)

    attempt.save(
        update_fields=["attempt_count", "response_code", "status", "last_error", "updated_at"]
    )
