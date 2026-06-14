from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from integrations.models import PartnerSource, WebhookSubscription
from tenants.models import Membership, Organization


class Command(BaseCommand):
    help = "Create a synthetic organization, user, source, and webhook subscription."

    def handle(self, *args, **options):
        organization, _ = Organization.objects.get_or_create(
            slug="synthetic-partner-hub",
            defaults={"name": "Synthetic Partner Hub"},
        )
        user, _ = get_user_model().objects.get_or_create(username="demo-developer")
        user.set_password("demo1234")
        user.save(update_fields=["password"])
        Membership.objects.update_or_create(
            organization=organization,
            user=user,
            defaults={"role": Membership.Role.DEVELOPER},
        )
        PartnerSource.objects.get_or_create(
            key="synthetic-source",
            defaults={
                "organization": organization,
                "name": "Synthetic Source",
                "signing_secret": "demo-inbound-secret",
            },
        )
        WebhookSubscription.objects.get_or_create(
            organization=organization,
            name="Synthetic Consumer",
            defaults={
                "url": "https://example.invalid/webhook",
                "signing_secret": "demo-outbound-secret",
            },
        )
        self.stdout.write(self.style.SUCCESS("Synthetic integration demo created."))
