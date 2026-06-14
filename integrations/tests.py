import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from tenants.models import Membership, Organization
from .models import DeliveryAttempt, InboundEvent, PartnerSource, WebhookSubscription
from .services import compute_signature
from .tasks import deliver_webhook


class IngestEventApiTests(APITestCase):
    def setUp(self):
        self.organization = Organization.objects.create(name="Synthetic Partner Hub", slug="synthetic-partner-hub")
        self.source = PartnerSource.objects.create(
            organization=self.organization,
            name="Synthetic Source",
            key="synthetic-source",
            signing_secret="inbound-secret",
        )
        self.subscription = WebhookSubscription.objects.create(
            organization=self.organization,
            name="Synthetic Consumer",
            url="https://example.invalid/webhook",
            signing_secret="outbound-secret",
        )
        self.body = json.dumps(
            {
                "event_type": "artifact.ready",
                "entity_id": "SYNTH-001",
                "data": {"artifact": "manifest.csv"},
            }
        ).encode("utf-8")

    @patch("integrations.views.deliver_webhook.delay")
    def test_accepts_signed_event_and_creates_delivery(self, delay):
        signature = compute_signature(self.source.signing_secret, self.body)

        response = self.client.post(
            "/api/ingest/synthetic-source/",
            data=self.body,
            content_type="application/json",
            HTTP_X_EVENT_ID="event-001",
            HTTP_X_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        event = InboundEvent.objects.get()
        self.assertEqual(event.normalized_payload["entity_id"], "SYNTH-001")
        attempt = DeliveryAttempt.objects.get()
        delay.assert_called_once_with(attempt.id)

    @patch("integrations.views.deliver_webhook.delay")
    def test_returns_existing_event_for_duplicate_idempotency_key(self, delay):
        signature = compute_signature(self.source.signing_secret, self.body)
        kwargs = {
            "data": self.body,
            "content_type": "application/json",
            "HTTP_X_EVENT_ID": "event-001",
            "HTTP_X_SIGNATURE": signature,
        }

        first = self.client.post("/api/ingest/synthetic-source/", **kwargs)
        second = self.client.post("/api/ingest/synthetic-source/", **kwargs)

        self.assertEqual(first.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertTrue(second.data["duplicate"])
        self.assertEqual(InboundEvent.objects.count(), 1)
        self.assertEqual(delay.call_count, 1)

    def test_rejects_invalid_signature(self):
        response = self.client.post(
            "/api/ingest/synthetic-source/",
            data=self.body,
            content_type="application/json",
            HTTP_X_EVENT_ID="event-001",
            HTTP_X_SIGNATURE="invalid",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(InboundEvent.objects.exists())


class SourceManagementApiTests(APITestCase):
    def test_viewer_cannot_create_source(self):
        user = get_user_model().objects.create_user(username="viewer", password="test-pass")
        organization = Organization.objects.create(name="Synthetic Partner Hub", slug="synthetic-partner-hub")
        Membership.objects.create(
            organization=organization,
            user=user,
            role=Membership.Role.VIEWER,
        )
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/sources/",
            {
                "organization": organization.id,
                "name": "Blocked Source",
                "key": "blocked-source",
                "signing_secret": "secret",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class DeliverWebhookTaskTests(TestCase):
    def setUp(self):
        organization = Organization.objects.create(name="Synthetic Partner Hub", slug="synthetic-partner-hub")
        source = PartnerSource.objects.create(
            organization=organization,
            name="Synthetic Source",
            key="synthetic-source",
            signing_secret="inbound-secret",
        )
        event = InboundEvent.objects.create(
            source=source,
            idempotency_key="event-001",
            event_type="artifact.ready",
            entity_id="SYNTH-001",
            payload={"data": {}},
            normalized_payload={"event_type": "artifact.ready", "entity_id": "SYNTH-001", "data": {}},
        )
        subscription = WebhookSubscription.objects.create(
            organization=organization,
            name="Synthetic Consumer",
            url="https://example.invalid/webhook",
            signing_secret="outbound-secret",
        )
        self.attempt = DeliveryAttempt.objects.create(event=event, subscription=subscription)

    @patch("integrations.tasks.requests.post")
    def test_marks_successful_delivery(self, post):
        post.return_value = Mock(status_code=204)

        deliver_webhook(self.attempt.id)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, DeliveryAttempt.Status.DELIVERED)
        self.assertEqual(self.attempt.attempt_count, 1)

    @patch("integrations.tasks.requests.post")
    def test_moves_repeated_failures_to_dead_letter(self, post):
        post.return_value = Mock(status_code=500)

        for _ in range(3):
            deliver_webhook(self.attempt.id)

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.status, DeliveryAttempt.Status.DEAD_LETTER)
        self.assertEqual(self.attempt.attempt_count, 3)

    @patch("integrations.tasks.requests.post")
    def test_does_not_redeliver_terminal_attempt(self, post):
        self.attempt.status = DeliveryAttempt.Status.DELIVERED
        self.attempt.save(update_fields=["status"])

        deliver_webhook(self.attempt.id)

        post.assert_not_called()
