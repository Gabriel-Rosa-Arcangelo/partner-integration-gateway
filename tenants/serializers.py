from rest_framework import serializers

from .models import Membership


class MembershipSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)

    class Meta:
        model = Membership
        fields = ["organization", "organization_name", "organization_slug", "role"]


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    memberships = MembershipSerializer(source="gateway_memberships", many=True)
