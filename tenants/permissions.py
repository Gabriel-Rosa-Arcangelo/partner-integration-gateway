from rest_framework.exceptions import PermissionDenied

from .models import Membership, Organization

MANAGER_ROLES = [Membership.Role.ADMIN, Membership.Role.DEVELOPER]


def organization_ids_for_user(user):
    if not user.is_authenticated:
        return []
    return Membership.objects.filter(user=user).values_list("organization_id", flat=True)


def require_organization_role(user, organization: Organization, roles=None):
    roles = roles or list(Membership.Role.values)
    if not Membership.objects.filter(user=user, organization=organization, role__in=roles).exists():
        raise PermissionDenied("You do not have permission for this organization.")
