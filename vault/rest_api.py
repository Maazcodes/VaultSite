# pylint: disable=too-many-ancestors

from urllib import parse

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.utils.encoding import uri_to_iri
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
from django.http import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.urls import (
    get_script_prefix,
    resolve,
)

from django_filters import filterset
from django_filters.filterset import FilterSet
from django_filters.rest_framework import DjangoFilterBackend
from django_filters import (
    ModelChoiceFilter,
    ModelMultipleChoiceFilter,
    NumberFilter,
)

from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import (
    BrowsableAPIRenderer,
    JSONRenderer,
)
from rest_framework.routers import DefaultRouter
from rest_framework.views import exception_handler as _exception_handler
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import (
    CreateModelMixin,
    DestroyModelMixin,
    ListModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
)
from rest_framework.serializers import (
    HyperlinkedModelSerializer,
    ListSerializer,
)
from rest_framework import status

from vault.helpers import safe_parse_int
from vault.models import (
    Collection,
    Geolocation,
    Organization,
    Plan,
    TreeNode,
    TreeNodeException,
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
DATE_TIME_FORMAT = "%B %-d, %Y %H:%M:%S UTC"

###############################################################################
# Exception Handler
###############################################################################


def exception_handler(exc, context):
    # Call REST framework's default exception handler first,
    # to get the standard error response.
    response = _exception_handler(exc, context)
    if response is not None:
        return response

    if isinstance(exc, IntegrityError):
        # Handle unique constraint violations.
        if exc.args[0].startswith("duplicate key value violates unique constraint"):
            # 409 - Conflict: https://www.rfc-editor.org/rfc/rfc7231#section-6.5.8
            return Response(
                {"detail": "request violates unique constraint"}, status=409
            )

    return None


###############################################################################
# Custom BrowsableAPIRenderer Subclass
###############################################################################


class FormlessBrowsableAPIRenderer(BrowsableAPIRenderer):
    """Renders the browsable api, but excludes the forms."""

    def show_form_for_method(self, *args, **kwargs):
        return False


###############################################################################
# Custom HyperlinkedModelSerializer Base Class
###############################################################################


class VaultHyperlinkedModelSerializer(HyperlinkedModelSerializer):
    @classmethod
    def get_url(cls, request, instance):
        return cls(instance, context={"request": request})["url"].value


###############################################################################
# Serializers
###############################################################################


class GeolocationSerializer(VaultHyperlinkedModelSerializer):
    class Meta:
        model = Geolocation
        fields = (
            "name",
            "url",
        )


class CollectionSerializer(VaultHyperlinkedModelSerializer):
    class Meta:
        model = Collection
        fields = (
            "fixity_frequency",
            "name",
            "organization",
            "target_replication",
            "tree_node",
            "url",
        )


class OrganizationSerializer(VaultHyperlinkedModelSerializer):
    class Meta:
        model = Organization
        fields = (
            "name",
            "plan",
            "quota_bytes",
            "tree_node",
            "url",
        )


class PlanSerializer(VaultHyperlinkedModelSerializer):
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


class UserSerializer(VaultHyperlinkedModelSerializer):
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


class MinimalUserSerializer(VaultHyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = (
            "url",
            "username",
        )


class TreeNodeSerializer(VaultHyperlinkedModelSerializer):
    uploaded_by = MinimalUserSerializer(read_only=True)

    class Meta:
        model = TreeNode
        fields = [
            "name",
            "node_type",
            "file_type",
            "size",
            "uploaded_at",
            "pre_deposit_modified_at",
            "modified_at",
            "uploaded_by",
            "md5_sum",
            "sha1_sum",
            "sha256_sum",
            "id",
            "comment",
            "parent",
            "path",
            "url",
            "content_url",
        ]
        read_only_fields = ["content_url"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["uploaded_at"] = (
            instance.uploaded_at.strftime(DATE_TIME_FORMAT)
            if instance.uploaded_at
            else ""
        )
        representation["modified_at"] = (
            instance.modified_at.strftime(DATE_TIME_FORMAT)
            if instance.modified_at
            else ""
        )
        representation["pre_deposit_modified_at"] = (
            instance.pre_deposit_modified_at.strftime(DATE_TIME_FORMAT)
            if instance.pre_deposit_modified_at
            else ""
        )
        return representation

    @classmethod
    def setup_eager_loading(cls, queryset):
        """Prefetch related fields to minimize the number of queries."""
        return queryset.prefetch_related("uploaded_by")


###############################################################################
# Custom ViewSet Base Classes
###############################################################################


class VaultReadOnlyModelViewSet(GenericViewSet, ListModelMixin, RetrieveModelMixin):
    """
    GenericViewSet subclass w/ List + Retrieve mixins that implements:

    - Additional GET param support

      - *__exact/gt/gte/lt/lte lookups for numeric fields

      - *__exact/contains/endswith/... lookups for text fields
        See FILTERSET_TEXT_SPEC for the full list.

      - __depth=N for specifying foreign key lookup depth

    """

    permission_classes = (IsAuthenticated,)
    filter_backends = (DjangoFilterBackend, OrderingFilter)
    renderer_classes = (JSONRenderer, FormlessBrowsableAPIRenderer)

    """A read-only viewset that implements list() and retrieve() methods."""

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Assert that filterset_class is defined."""
        filterset_class = getattr(cls, "filterset_class", None)
        if filterset_class is None or not issubclass(filterset_class, FilterSet):
            raise AssertionError(
                f"{cls.__name__} needs to define a valid filterset_class"
            )
        super().__init_subclass__(**kwargs)

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

    @staticmethod
    def normalize_hyperlinkedrelatedfield_url(url):
        """Return a HyperlinkedRelatedField URL as a app-root relative path.
        Adapted from: https://github.com/encode/django-rest-framework/blob/02eeb6fa003b5cbe3851ac18392f129d31a1a6bd/rest_framework/relations.py#L343-L355
        """  # pylint: disable=line-too-long
        try:
            http_prefix = url.startswith(("http:", "https:"))
        except AttributeError:
            return None

        if http_prefix:
            # If needed convert absolute URLs to relative path
            url = parse.urlparse(url).path
            prefix = get_script_prefix()
            if url.startswith(prefix):
                url = "/" + url[len(prefix) :]

        return uri_to_iri(parse.unquote(url))

    def get_by_url(self, user, url):
        """Attempt to return the model instance indicated by a
        HyperlinkedModelSerializer-generated URL by first applying any specified
        FilterSet.Meta.user_queryset_filter function. DoesNotExist will be raised
        if user_queryset_filter prevents the get.
        """
        # pylint: disable=no-member

        # Normalize the URL to an app-root relative path.
        url = self.normalize_hyperlinkedrelatedfield_url(url)
        if url is None:
            raise ObjectDoesNotExist

        pk = int(resolve(url).kwargs["pk"])
        model = self.serializer_class.Meta.model

        if not hasattr(self, "filterset_class"):
            return model.get(pk=pk)

        queryset = model.objects.all()
        user_queryset_filter = getattr(
            self.filterset_class.Meta, "user_queryset_filter"
        )
        if user_queryset_filter:
            queryset = user_queryset_filter(user, queryset)
        return queryset.get(pk=pk)


class VaultUpdateModelMixin(UpdateModelMixin):
    """A UpdateModelMixin subclass that overrides update() to protect immutable fields."""

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """Assert that mutable_fields is defined."""
        if getattr(cls, "mutable_fields", None) is None:
            raise AssertionError(f"{cls.__name__} needs to define mutable_fields")
        super().__init_subclass__(**kwargs)

    def update(self, request, *args, **kwargs):
        """Check self.mutatble_fields against the request data object's keys and respond
        with a 403 if any immutable field was specified."""
        immutable_fields = set(request.data.keys()).difference(self.mutable_fields)
        if immutable_fields:
            return Response(
                f"Immutable field(s) can not be updated: {immutable_fields}",
                status=403,
            )
        return super().update(request, *args, **kwargs)


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
        # pylint: disable=no-member

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
        # pylint: disable=no-member

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
        # pylint: disable=no-member

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
                # We're specifying a ForeignKey override via Meta.filter_overrides
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

        def func(request):
            user_queryset_filter = cls.model_user_queryset_filter_map[model]
            return user_queryset_filter(request.user, model.objects.all())

        return func

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
        """  # pylint: disable=line-too-long
        override_filter_classes = (ModelChoiceFilter, ModelMultipleChoiceFilter)
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
            if obj["filter_class"] in override_filter_classes
        }


class CollectionFilterSet(VaultFilterSet):
    # Use a number-type filter for tree_node instead of the default choice filter.
    tree_node = NumberFilter()

    class Meta:
        model = Collection
        fields = CollectionSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs.filter(
            organization__id=user.organization_id
        )


class GeolocationFilterSet(VaultFilterSet):
    class Meta:
        model = Geolocation
        fields = GeolocationSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs


class TreeNodeFilterSet(VaultFilterSet):
    # Use a number-type filter for parent instead of the default choice filter.
    parent = NumberFilter()

    class Meta:
        model = TreeNode
        fields = TreeNodeSerializer.Meta.fields
        user_queryset_filter = lambda user, qs: qs.filter(
            path__descendant=user.organization.tree_node.path,
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
# Views
###############################################################################


class CollectionViewSet(
    VaultReadOnlyModelViewSet, CreateModelMixin, VaultUpdateModelMixin
):
    queryset = Collection.objects.all()
    serializer_class = CollectionSerializer
    filterset_class = CollectionFilterSet
    mutable_fields = ("name", "fixity_frequency", "target_replication")

    @staticmethod
    def _organization_ok(user, organization_url):
        try:
            OrganizationViewSet().get_by_url(user, organization_url)
        except ObjectDoesNotExist:
            return False
        return True

    # Note that we don't need to override update() to implement an _organization_ok()
    # check because "organization" is not included in mutable_fields.

    def create(self, request, *args, **kwargs):
        """Override CreateModelMixin.create() to validate requests."""
        organization_url = request.data.get("organization")
        if organization_url:
            # Return a 403 if the specified Organization is not accessible by the user.
            if not self._organization_ok(request.user, organization_url):
                return Response(status=403)
        else:
            # Organization was not specified, so assume the user's org.
            request.data["organization"] = OrganizationSerializer.get_url(
                request, request.user.organization
            )
        return super().create(request, *args, **kwargs)


class GeolocationViewSet(VaultReadOnlyModelViewSet):
    queryset = Geolocation.objects.all()
    serializer_class = GeolocationSerializer
    filterset_class = GeolocationFilterSet


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


class TreeNodeViewSet(
    VaultReadOnlyModelViewSet,
    CreateModelMixin,
    VaultUpdateModelMixin,
    DestroyModelMixin,
):
    queryset = TreeNode.objects.all()
    serializer_class = TreeNodeSerializer
    ordering_fields = ("id", "name", "node_type")
    filterset_class = TreeNodeFilterSet
    mutable_fields = ("name", "parent")

    def _parent_ok(self, user, parent_url):
        try:
            self.get_by_url(user, parent_url)
        except ObjectDoesNotExist:
            return False
        return True

    def update(self, request, *args, **kwargs):
        """Override UpdateModelMixin.update() to validate that any specified parent is
        accessible by the requesting user.
        """
        if "parent" in request.data:
            if not self._parent_ok(request.user, request.data["parent"]):
                return Response(status=403)
        return super().update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Override CreateModelMixin.create() to validate requests."""
        if "node_type" not in request.data or "parent" not in request.data:
            return HttpResponseBadRequest("node_type and parent are required")
        if request.data["node_type"] != "FOLDER":
            return HttpResponseBadRequest(
                'Creation only enabled for node_type="FOLDER"'
            )

        # Return a 403 if the specified parent is not accessible by this user.
        if not self._parent_ok(request.user, request.data["parent"]):
            return HttpResponseForbidden()

        return super().create(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Soft DELETE of Treenode."""
        tree_node = self.get_object()

        try:
            tree_node.delete()
        except TreeNodeException as e:
            return Response(data=str(e), status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_200_OK)


###############################################################################
# Router
###############################################################################

router = DefaultRouter()
router.register("collections", CollectionViewSet)
router.register("geolocations", GeolocationViewSet)
router.register("organizations", OrganizationViewSet)
router.register("plans", PlanViewSet)
router.register("treenodes", TreeNodeViewSet)
router.register("users", UserViewSet)
