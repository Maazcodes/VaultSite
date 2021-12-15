from django.db.models import TextChoices
from django.db.models.fields import (
    BigAutoField,
    CharField,
    DateTimeField,
    DecimalField,
    IntegerField,
    PositiveBigIntegerField,
    PositiveSmallIntegerField,
    TextField,
)

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.routers import DefaultRouter
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import (
    UpdateModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
)
from rest_framework.serializers import (
    HyperlinkedModelSerializer,
    ListSerializer,
)

from vault.filters import ExtendedJSONEncoder
from vault.helpers import safe_parse_int
from vault.models import (
    Collection,
    Geolocation,
    Organization,
    Plan,
    TreeNode,
    User,
)


###############################################################################
# Constants
###############################################################################

NUMERIC_FIELD_CLASSES = (
    BigAutoField,
    DateTimeField,
    DecimalField,
    IntegerField,
    PositiveBigIntegerField,
    PositiveSmallIntegerField,
)

TEXT_FIELD_CLASSES = (CharField, TextField, TextChoices)


###############################################################################
# Serializers
###############################################################################


class GeolocationSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Geolocation
        fields = "__all__"


class OrganizationSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "name",
            "plan",
            "quota_bytes",
            "tree_node",
            "url",
        ]


class PlanSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Plan
        fields = "__all__"


class UserSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = User
        exclude = ("email", "groups", "password", "user_permissions")


class MinimalUserSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = (
            "url",
            "username",
        )


class TreeNodeSerializer(HyperlinkedModelSerializer):
    uploaded_by = MinimalUserSerializer(read_only=True)

    class Meta:
        model = TreeNode
        fields = [
            "id",
            "comment",
            "file_type",
            "modified_at",
            "name",
            "node_type",
            "parent",
            "path",
            "pre_deposit_modified_at",
            "sha1_sum",
            "sha256_sum",
            "size",
            "uploaded_at",
            "uploaded_by",
            "url",
        ]


###############################################################################
# Custom ViewSet Base Classes
###############################################################################


class VaultViewSet(GenericViewSet):
    """
    GenericViewSet subclass that implements:

    - Additional GET param support

      - *__exact/gt/gte/lt/lte lookups for numeric fields

      - *__exact/contains/endswith/... lookups for text fields
        See FILTERSET_TEXT_SPEC for the full list.

      - __depth=N for specifying foreign key lookup depth

    """

    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)

    FILTERSET_NUMBER_SPEC = (
        "exact",
        "gt",
        "gte",
        "lt",
        "lte",
    )
    FILTERSET_TEXT_SPEC = (
        "contains",
        "endswith",
        "exact",
        "icontains",
        "iexact",
        "startswith",
    )

    @classmethod
    def as_view(cls, actions=None, **initkwargs):
        # Hook the call to init_filterset_fields() in here.
        cls.init_filterset_fields()
        return super().as_view(actions, **initkwargs)

    @classmethod
    def init_filterset_fields(cls):
        """Auto-generate a django-filter filterset_fields spec that
        includes extra lookup expression params based on the field type.
        """
        filterset_fields = {}
        for field in cls.queryset.model._meta.fields:
            if isinstance(field, NUMERIC_FIELD_CLASSES):
                # Field is numeric.
                spec = cls.FILTERSET_NUMBER_SPEC
            elif isinstance(field, TEXT_FIELD_CLASSES):
                # Field is text.
                spec = cls.FILTERSET_TEXT_SPEC
            else:
                # Field is something else - don't enable filtering.
                continue
            filterset_fields[field.name] = spec
        cls.filterset_fields = filterset_fields

    def get_queryset(self):
        """Apply the user_queryset_filter() to the queryset."""
        user = self.request.user
        user_queryset_filter = self.__class__.user_queryset_filter
        if user_queryset_filter is None:
            return self.queryset
        return user_queryset_filter(user, self.queryset)

    def get_serializer(self, *args, **kwargs):
        """Apply request-specific serializer modifications."""
        serializer = super().get_serializer(*args, **kwargs)

        target_serializer = (
            serializer
            if not isinstance(serializer, ListSerializer)
            else serializer.child
        )

        # Some built-in serializers (e.g. ListSerializer) don't have Meta.
        depth_s = self.request.GET.get("__depth")
        target_serializer.Meta.depth = safe_parse_int(depth_s, 0, _min=0)

        return serializer


class VaultReadOnlyModelViewSet(
    VaultViewSet,
    ListModelMixin,
    RetrieveModelMixin,
):
    """A read-only viewset that implements list() and retrieve() methods."""

    pass


class VaultUpdateModelViewSet(VaultReadOnlyModelViewSet, UpdateModelMixin):
    """A viewset that extends VaultReadOnlyModelViewSet with an update()
    method.
    """

    pass


###############################################################################
# Public Views
###############################################################################


class GeolocationViewSet(VaultReadOnlyModelViewSet):
    queryset = Geolocation.objects.all()
    serializer_class = GeolocationSerializer
    permission_classes = (IsAuthenticated,)
    user_queryset_filter = None


###############################################################################
# Custom Responses
###############################################################################

JSONResponse = lambda data, **kwargs: Response(
    ExtendedJSONEncoder().encode(data), **kwargs
)


###############################################################################
# Protected Views
###############################################################################


class OrganizationViewSet(VaultReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    user_queryset_filter = lambda user, qs: qs.filter(id=user.organization_id)


class PlanViewSet(VaultReadOnlyModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    user_queryset_filter = lambda user, qs: qs.filter(
        organization__id=user.organization_id
    )


class UserViewSet(VaultReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    user_queryset_filter = lambda user, qs: qs.filter(id=user.id)


class TreeNodeViewSet(VaultReadOnlyModelViewSet):
    queryset = TreeNode.objects.all()
    serializer_class = TreeNodeSerializer
    ordering_fields = ["id", "name", "node_type"]
    # Specify the user's organization COLLECTION-nodes as the access
    # entrypoint.
    user_queryset_filter = lambda user, qs: qs.extra(
        where=[f"path <@ '{user.organization.tree_node.path}'"]
    )


###############################################################################
# Router
###############################################################################

router = DefaultRouter()
router.register("geolocations", GeolocationViewSet)
router.register("organizations", OrganizationViewSet)
router.register("plans", PlanViewSet)
router.register("treenodes", TreeNodeViewSet)
router.register("users", UserViewSet)
