from django.db.models import (
    ForeignKey,
    TextChoices,
)
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

from django_filters import filterset
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import (
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
    NumberFilter,
)
from django_filters.filterset import FilterSet

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
        fields = (
            "name",
            "url",
        )


class OrganizationSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "name",
            "plan",
            "quota_bytes",
            "tree_node",
            "url",
        )


class PlanSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = Plan
        fields = (
            "default_fixity_frequency",
            "default_geolocations",
            "default_replication",
            "name",
            "price_per_terabyte",
            "url",
        )


class UserSerializer(HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = (
            "date_joined",
            "first_name",
            "is_active",
            "is_staff",
            "is_superuser",
            "last_login",
            "last_name",
            "organization",
            "url",
            "username",
        )


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

    @classmethod
    def setup_eager_loading(cls, queryset):
        """Prefetch related fields to minimize the number of queries."""
        return queryset.prefetch_related("uploaded_by")


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

    def get_queryset(self):
        """Return a queryset with applied request-time transformations."""
        queryset = self.queryset

        # Get the serializer class.
        serializer_cls = self.get_serializer_class()

        # Perform any defined eager loading.
        # https://ses4j.github.io/2015/11/23/optimizing-slow-django-rest-framework-performance/
        if hasattr(serializer_cls, "setup_eager_loading"):
            queryset = serializer_cls.setup_eager_loading(queryset)

        return queryset

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


###############################################################################
# Custom FilterSets
###############################################################################


class VaultFilterSet(FilterSet):
    """
    FilterSet subclass that:

    - Adds gt, gte, ... lookups for numeric fields

    - Adds contains, endswith, ... lookups for text fields

    - Adds a filter override for ForeignKey fields using the ModelChoiceFilter
      with a queryset that's constrained by any defined user_queryset_filter
      on the target model's VaultFilterSet subclass.
    """

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

    # Define a place to store a model -> user_queryset_filter map.
    model_user_queryset_filter_map = {}

    @classmethod
    def __init_subclass__(cls, **kwargs):
        # Add this to the class model => user_queryset_filter map.
        VaultFilterSet.model_user_queryset_filter_map[
            cls.Meta.model
        ] = cls.Meta.user_queryset_filter

        # Rewrite fields and set filter_overrides.
        cls.Meta.fields = cls.build_filterset_fields()
        cls.Meta.filter_overrides = cls.get_filter_overrides()

        super().__init_subclass__(**kwargs)

    @property
    def qs(self):
        """Override FilterSet.qs to apply any defined user_queryset_filter to the
        queryset.
        """
        queryset = super().qs
        user_queryset_filter = self.__class__.Meta.user_queryset_filter
        if user_queryset_filter is None:
            return queryset
        return user_queryset_filter(self.request.user, queryset)

    @classmethod
    def build_filterset_fields(cls):
        """Auto-generate a django-filter filterset_fields spec that
        includes extra lookup expression params based on the field type.
        """
        # Get any defined Meta.fields value.
        fields = getattr(cls.Meta, "fields", ())

        # Assert that any defined Meta.fields is a tuple or list as opposed to a
        # dict, which is not currently supported.
        if not isinstance(fields, (tuple, list)):
            raise AssertionError(
                "Only tuple or list-type Serializer.Meta.fields values are supported"
            )

        # Determine the set of fields to include.
        include_names = set(
            fields or (x.name for x in cls.Meta.model._meta.fields)
        ).difference(getattr(cls.Meta, "exclude", ()))

        declared_filter_field_names = set(cls.declared_filters.keys())

        fields = {}
        for field in cls.Meta.model._meta.fields:
            # Check whether we should include this field.
            if field.name not in include_names:
                continue
            if isinstance(field, NUMERIC_FIELD_CLASSES):
                # Field is numeric.
                spec = cls.FILTERSET_NUMBER_SPEC
            elif isinstance(field, TEXT_FIELD_CLASSES):
                # Field is text.
                spec = cls.FILTERSET_TEXT_SPEC
            elif (
                isinstance(field, ForeignKey)
                and field.name not in declared_filter_field_names
            ):
                # Field is a ForeignKey and was not declared as a top-level
                # FilterSet attribute (i.e. override).
                # We're specifying a ForeignKey override via Meta.filter_overrides in
                # in __init__() but we need to include the field in fields in order
                # for it to take effect.
                spec = ("exact",)
            else:
                # Field is something else - don't enable filtering.
                continue
            fields[field.name] = spec
        return fields

    @classmethod
    def get_fk_override_queryset_func(cls, model):
        """Return a queryset function that takes a request argument and returns
        a queryset for the specified model filtered by any user_queryset_filter
        defined on the corresponding model's VaultFilterSet subclass.
        """

        def f(request):
            user_queryset_filter = cls.model_user_queryset_filter_map[model]
            return user_queryset_filter(request.user, model.objects.all())

        return f

    @classmethod
    def get_filter_overrides(cls):
        """Return a FilterSet.Meta.filter_overrides dict that overrides the field types
        that django-filters automatically defaults of ModelChoiceFilter or
        ModelMultipleChoice with an unfiltered model queryset to instead use a queryset
        that constrained by any defined user_queryset_filter.

        See:
          - https://django-filter.readthedocs.io/en/stable/ref/filterset.html?highlight=filter_override#filter-overrides
          - https://django-filter.readthedocs.io/en/stable/ref/filters.html?highlight=modelchoicefilter#modelchoicefilter
          - https://github.com/carltongibson/django-filter/blob/3635b2b67c110627e74404603330583df0000a44/django_filters/filterset.py#L149-L156
        """
        OVERRIDE_FILTER_CLASSES = (ModelChoiceFilter, ModelMultipleChoiceFilter)
        return {
            field_class: {
                "filter_class": obj["filter_class"],
                "extra": lambda field: {
                    "queryset": cls.get_fk_override_queryset_func(
                        field.target_field.model
                    )
                },
            }
            for field_class, obj in filterset.FILTER_FOR_DBFIELD_DEFAULTS.items()
            if obj["filter_class"] in OVERRIDE_FILTER_CLASSES
        }


class TreeNodeFilterSet(VaultFilterSet):
    # Use a number-type filter for parent instead of the default choice filter.
    parent = NumberFilter()

    class Meta:
        model = TreeNode
        fields = TreeNodeSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs.extra(
            where=[f"path <@ '{user.organization.tree_node.path}'"]
        )


class OrganizationFilterSet(VaultFilterSet):
    # Use a number-type filter for tree_node instead of the default choice filter.
    tree_node = NumberFilter()

    class Meta:
        model = Organization
        fields = OrganizationSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs.filter(id=user.organization_id)


class UserFilterSet(VaultFilterSet):
    class Meta:
        model = User
        fields = UserSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs.filter(id=user.id)


class PlanFilterSet(VaultFilterSet):
    class Meta:
        model = Plan
        fields = PlanSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs.filter(
            organization__id=user.organization_id
        )


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
    filterset_class = OrganizationFilterSet


class PlanViewSet(VaultReadOnlyModelViewSet):
    queryset = Plan.objects.all()
    serializer_class = PlanSerializer
    filterset_class = PlanFilterSet


class UserViewSet(VaultReadOnlyModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    filterset_class = UserFilterSet


class TreeNodeViewSet(VaultReadOnlyModelViewSet):
    queryset = TreeNode.objects.all()
    serializer_class = TreeNodeSerializer
    ordering_fields = ["id", "name", "node_type"]
    filterset_class = TreeNodeFilterSet


###############################################################################
# Router
###############################################################################

router = DefaultRouter()
router.register("geolocations", GeolocationViewSet)
router.register("organizations", OrganizationViewSet)
router.register("plans", PlanViewSet)
router.register("treenodes", TreeNodeViewSet)
router.register("users", UserViewSet)
