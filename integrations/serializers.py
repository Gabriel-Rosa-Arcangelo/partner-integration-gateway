from rest_framework import serializers

from .models import DeliveryAttempt, InboundEvent, PartnerSource, WebhookSubscription


class PartnerSourceSerializer(serializers.ModelSerializer):
    signing_secret = serializers.CharField(write_only=True)

    class Meta:
        model = PartnerSource
        fields = ["id", "organization", "name", "key", "signing_secret", "active", "created_at"]
        read_only_fields = ["id", "created_at"]


class WebhookSubscriptionSerializer(serializers.ModelSerializer):
    signing_secret = serializers.CharField(write_only=True)

    class Meta:
        model = WebhookSubscription
        fields = ["id", "organization", "name", "url", "signing_secret", "active", "created_at"]
        read_only_fields = ["id", "created_at"]


class InboundEventSerializer(serializers.ModelSerializer):
    source_key = serializers.CharField(source="source.key", read_only=True)

    class Meta:
        model = InboundEvent
        fields = [
            "id",
            "source",
            "source_key",
            "idempotency_key",
            "event_type",
            "entity_id",
            "payload",
            "normalized_payload",
            "status",
            "received_at",
        ]


class DeliveryAttemptSerializer(serializers.ModelSerializer):
    subscription_name = serializers.CharField(source="subscription.name", read_only=True)

    class Meta:
        model = DeliveryAttempt
        fields = [
            "id",
            "event",
            "subscription",
            "subscription_name",
            "status",
            "attempt_count",
            "response_code",
            "last_error",
            "updated_at",
        ]


class IngestEventRequestSerializer(serializers.Serializer):
    event_type = serializers.CharField(max_length=100)
    entity_id = serializers.CharField(max_length=120)
    data = serializers.DictField()


class IngestEventResponseSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    duplicate = serializers.BooleanField()
