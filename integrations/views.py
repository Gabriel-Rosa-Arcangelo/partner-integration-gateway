from drf_spectacular.utils import extend_schema
from django.db import IntegrityError
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from tenants.permissions import MANAGER_ROLES, organization_ids_for_user, require_organization_role
from .models import DeliveryAttempt, InboundEvent, PartnerSource, WebhookSubscription
from .serializers import (
    DeliveryAttemptSerializer,
    InboundEventSerializer,
    IngestEventRequestSerializer,
    IngestEventResponseSerializer,
    PartnerSourceSerializer,
    WebhookSubscriptionSerializer,
)
from .services import normalize_event, signature_is_valid
from .tasks import deliver_webhook


class ScopedManagementViewSet(viewsets.ModelViewSet):
    organization_field = "organization"

    def perform_create(self, serializer):
        organization = serializer.validated_data["organization"]
        require_organization_role(self.request.user, organization, MANAGER_ROLES)
        serializer.save()

    def perform_update(self, serializer):
        organization = getattr(serializer.instance, self.organization_field)
        require_organization_role(self.request.user, organization, MANAGER_ROLES)
        serializer.save()

    def perform_destroy(self, instance):
        organization = getattr(instance, self.organization_field)
        require_organization_role(self.request.user, organization, MANAGER_ROLES)
        instance.delete()


class PartnerSourceViewSet(ScopedManagementViewSet):
    serializer_class = PartnerSourceSerializer

    def get_queryset(self):
        return PartnerSource.objects.filter(
            organization_id__in=organization_ids_for_user(self.request.user)
        ).select_related("organization")


class WebhookSubscriptionViewSet(ScopedManagementViewSet):
    serializer_class = WebhookSubscriptionSerializer

    def get_queryset(self):
        return WebhookSubscription.objects.filter(
            organization_id__in=organization_ids_for_user(self.request.user)
        ).select_related("organization")


class InboundEventViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = InboundEventSerializer

    def get_queryset(self):
        return InboundEvent.objects.filter(
            source__organization_id__in=organization_ids_for_user(self.request.user)
        ).select_related("source", "source__organization")


class DeliveryAttemptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = DeliveryAttemptSerializer

    def get_queryset(self):
        return DeliveryAttempt.objects.filter(
            subscription__organization_id__in=organization_ids_for_user(self.request.user)
        ).select_related("event", "subscription", "subscription__organization")


class IngestEventView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=IngestEventRequestSerializer,
        responses={
            status.HTTP_202_ACCEPTED: IngestEventResponseSerializer,
            status.HTTP_200_OK: IngestEventResponseSerializer,
        },
    )
    def post(self, request, source_key):
        source = PartnerSource.objects.filter(key=source_key, active=True).select_related("organization").first()
        if source is None:
            return Response({"detail": "Source not found."}, status=status.HTTP_404_NOT_FOUND)

        event_key = request.headers.get("X-Event-ID", "")
        signature = request.headers.get("X-Signature", "")
        if not event_key or not signature:
            return Response(
                {"detail": "X-Event-ID and X-Signature headers are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not signature_is_valid(source.signing_secret, request.body, signature):
            return Response({"detail": "Invalid signature."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = IngestEventRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        normalized = normalize_event(
            source_key=source.key,
            event_type=serializer.validated_data["event_type"],
            entity_id=serializer.validated_data["entity_id"],
            data=serializer.validated_data["data"],
        )
        try:
            event, created = InboundEvent.objects.get_or_create(
                source=source,
                idempotency_key=event_key,
                defaults={
                    "event_type": serializer.validated_data["event_type"],
                    "entity_id": serializer.validated_data["entity_id"],
                    "payload": serializer.validated_data,
                    "normalized_payload": normalized,
                },
            )
        except IntegrityError:
            event = InboundEvent.objects.get(source=source, idempotency_key=event_key)
            created = False
        if not created:
            return Response(
                {"id": event.id, "status": event.status, "duplicate": True},
                status=status.HTTP_200_OK,
            )

        for subscription in source.organization.webhook_subscriptions.filter(active=True):
            attempt = DeliveryAttempt.objects.create(event=event, subscription=subscription)
            deliver_webhook.delay(attempt.id)

        return Response(
            {"id": event.id, "status": event.status, "duplicate": False},
            status=status.HTTP_202_ACCEPTED,
        )
