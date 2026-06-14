import uuid

from django.db import models

from tenants.models import Organization


class PartnerSource(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="partner_sources")
    name = models.CharField(max_length=120)
    key = models.SlugField(unique=True)
    signing_secret = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class InboundEvent(models.Model):
    class Status(models.TextChoices):
        NORMALIZED = "NORMALIZED", "Normalized"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(PartnerSource, on_delete=models.CASCADE, related_name="events")
    idempotency_key = models.CharField(max_length=120)
    event_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=120)
    payload = models.JSONField()
    normalized_payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NORMALIZED)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        constraints = [
            models.UniqueConstraint(fields=["source", "idempotency_key"], name="unique_source_event_key")
        ]


class WebhookSubscription(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="webhook_subscriptions")
    name = models.CharField(max_length=120)
    url = models.URLField()
    signing_secret = models.CharField(max_length=255)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class DeliveryAttempt(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        DELIVERED = "DELIVERED", "Delivered"
        FAILED = "FAILED", "Failed"
        DEAD_LETTER = "DEAD_LETTER", "Dead letter"

    event = models.ForeignKey(InboundEvent, on_delete=models.CASCADE, related_name="delivery_attempts")
    subscription = models.ForeignKey(
        WebhookSubscription,
        on_delete=models.CASCADE,
        related_name="delivery_attempts",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveIntegerField(default=0)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["event", "subscription"], name="unique_event_subscription_delivery")
        ]
