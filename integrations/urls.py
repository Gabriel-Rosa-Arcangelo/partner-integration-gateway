from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryAttemptViewSet,
    InboundEventViewSet,
    IngestEventView,
    PartnerSourceViewSet,
    WebhookSubscriptionViewSet,
)

router = DefaultRouter()
router.register("sources", PartnerSourceViewSet, basename="source")
router.register("subscriptions", WebhookSubscriptionViewSet, basename="subscription")
router.register("events", InboundEventViewSet, basename="event")
router.register("deliveries", DeliveryAttemptViewSet, basename="delivery")

urlpatterns = [path("ingest/<slug:source_key>/", IngestEventView.as_view(), name="ingest-event")]
urlpatterns += router.urls
