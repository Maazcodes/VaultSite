from pytest import fixture, mark, raises

import lxml.html
from django.forms import model_to_dict
from model_bakery import baker
from rest_framework.test import APIClient
import rest_framework.relations

from vault.filters import ExtendedJSONEncoder
from vault.models import (
    Collection,
    Organization,
    TreeNode,
)
import vault.rest_api
from vault.rest_api import (
    CollectionFilterSet,
    CollectionViewSet,
    GeolocationViewSet,
    TreeNodeViewSet,
    VaultReadOnlyModelViewSet,
    VaultUpdateModelMixin,
)


###############################################################################
# Constants
###############################################################################


VALID_RESOURCE_NAMES = {
    "collections",
    "geolocations",
    "organizations",
    "plans",
    "treenodes",
    "users",
}


###############################################################################
# Fixtures
###############################################################################


@fixture
def users(make_user, make_staff_user, make_super_user):
    """Return a tuple comprising one of each type of user."""
    return (
        make_user(),
        make_staff_user(),
        make_super_user(),
    )


@fixture
def user_and_child_node(user, make_treenode):
    child_node = make_treenode(
        node_type="COLLECTION", parent=user.organization.tree_node
    )
    return user, child_node


###############################################################################
# Helpers
###############################################################################


class AuthenticatedClient(APIClient):
    """User-specific APIClient subclass with automatic user authentication."""

    def __init__(self, user):
        super().__init__()
        # Save the user for convenience.
        self.user = user
        self.force_login(self.user)

    def get_html(self, *args, **kwargs):
        return self.get(*args, HTTP_ACCEPT="text/html", **kwargs)

    def patch(self, *args, **kwargs):
        """Call APIClient.patch() with format=json."""
        return super().patch(*args, format="json", **kwargs)

    def post(self, *args, **kwargs):
        """Call APIClient.post() with format=json."""
        return super().post(*args, format="json", **kwargs)


def assert_404(response):
    """Assert a 404 status API response."""
    assert response.status_code == 404


def endpoint(resource_name, resource_id=None):
    """Return the API endpoint path for a specified resource."""
    assert resource_name in VALID_RESOURCE_NAMES
    if resource_id is None:
        return f"/api/{resource_name}/"
    else:
        return f"/api/{resource_name}/{resource_id}/"


def assert_hyperlinked_url(url, resource_name, resource_id):
    """Assert that a HyperlinkedModelSerializer URL is as expected."""
    assert url.endswith(endpoint(resource_name, resource_id))


def get_endpoint_html_filter_selects(user, _endpoint):
    """Return a list of <select> element nodes in the Filters dialog form
    at the specified endpoint.
    """
    client = AuthenticatedClient(user)
    html = client.get_html(endpoint(_endpoint)).content
    el = lxml.html.fromstring(html)
    return el.cssselect("div.modal-body > form select")


def assert_option_element_is_initial_empty_placeholder(option):
    """Assert that an option etree element is an empty initial placeholder."""
    assert option.get("value") == ""
    assert set(option.text) == {"-"}


###############################################################################
# Tests
###############################################################################

#### Required Subclass Attribute Tests ####


def test_VaultReadOnlyModelViewSet_must_define_filterset_class():
    """Test that subclassing VaultReadOnlyModelViewSet without defining
    filterset_class raises an AssertionError."""
    # Check that an undefined filterset_class raises an error.
    with raises(AssertionError):

        class C(VaultReadOnlyModelViewSet):
            pass

    # Check that an non-subclass-of-FilterSet filterset_class value raises an error.
    with raises(AssertionError):

        class C(VaultReadOnlyModelViewSet):
            filterset_class = None

    # Check a valid value.
    class C(VaultReadOnlyModelViewSet):
        filterset_class = CollectionFilterSet


def test_VaultUpdateModelMixin_must_define_mutable_fields():
    """Test that subclassing VaultUpdateModelMixin without defining mutable_fields
    raises an AssertionError."""
    with raises(AssertionError):

        class C(VaultUpdateModelMixin):
            pass

    # Test a valid value.
    class C(VaultUpdateModelMixin):
        mutable_fields = ()


#### VaultReadOnlyModelViewSet Utility Tests ####


def test_VaultReadOnlyModelViewSet_normalize_hyperlinkedrelatedfield_url(monkeypatch):
    """Test that VaultReadOnlyModelViewSet.normalize_hyperlinkedrelatedfield_url() converts
    URLs to app-root relative paths."""
    # Expect the same result for each input.
    expected = "/api/treenodes/1/"
    # Check that Django can resolve the expected, normalized path.
    for url, script_name in (
        # HTTP + no script name
        ("http://vault-site/api/treenodes/1/", None),
        # HTTPS + no script name
        ("https://vault-site/api/treenodes/1/", None),
        # HTTP + script name with trailing slash
        ("http://vault-site/vault/api/treenodes/1/", "/vault/"),
        # HTTPS + script name with trailing slash
        ("https://vault-site/vault/api/treenodes/1/", "/vault/"),
        # Relative + no script name
        ("/api/treenodes/1/", None),
    ):
        monkeypatch.setattr(
            vault.rest_api, "get_script_prefix", lambda: script_name or "/"
        )
        result = VaultReadOnlyModelViewSet.normalize_hyperlinkedrelatedfield_url(url)
        assert result == expected


#### Collections Endpoint Tests ####


@mark.django_db
def test_collections_endpoint_retrieval_access(make_user, users, make_collection):
    """Test that a user can retrieve its own organization's Collection objects but not
    those of others organizations."""
    # Create a new user and test retrieving its organization tree_node object.
    user = make_user()
    client = AuthenticatedClient(user)

    # Add a Collection to the user's organization tree node.
    collection = make_collection(organization=user.organization)

    # Test that the user can retrieve all nodes.
    _collection = client.get(endpoint("collections", collection.id)).json()
    assert_hyperlinked_url(_collection["url"], "collections", collection.id)

    # Assert that no other user is allowed to retrieve any of the user's nodes.
    for other_user in users:
        other_client = AuthenticatedClient(other_user)
        assert_404(other_client.get(endpoint("collections", collection.id)))


@mark.django_db
def test_collections_endpoint_list_access(users, make_collection):
    """Test that each user can only access collections that are owned by their
    organization."""
    # Create a collection with each user's organization.
    user_id_collection_id_map = {
        user.id: make_collection(organization=user.organization).id for user in users
    }

    # Instantiate an AuthenticatedClient for each user.
    clients = [AuthenticatedClient(user) for user in users]

    # Test retrieving all organization collections ordered by ID ascending.
    for client in clients:
        response = client.get(endpoint("collections")).json()
        assert response["count"] == 1
        assert_hyperlinked_url(
            response["results"][0]["url"],
            "collections",
            user_id_collection_id_map[client.user.id],
        )


@mark.django_db
def test_collections_endpoint_list_html_filters(users):
    """Test that dropdowns in the collections endpoint HTML response Filters dialog
    form contain only authorized values.
    """
    for user in users:
        selects = get_endpoint_html_filter_selects(user, "collections")
        # Assert that there are organization, targest replication, and fixity
        # frequency selects.
        name_select_map = {x.name: x for x in selects}
        assert set(name_select_map) == {
            "organization",
            "target_replication",
            "fixity_frequency",
        }
        # Check that non-placeholder organization options comprise the single
        # requesting user's organization.
        options = name_select_map["organization"].getchildren()
        assert_option_element_is_initial_empty_placeholder(options[0])
        assert int(options[1].get("value")) == user.organization.id


@mark.django_db
def test_collections_endpoint_create_allowed(users, make_organization):
    """Test that the collections endpoint allow creation."""
    # Create a unique organization to serve as an unauthorized value.
    other_organization = make_organization()

    for user in users:
        client = AuthenticatedClient(user)

        # Check a collection can be created with the organization inferred from
        # the requesting user.
        collection_dict = model_to_dict(baker.prepare(Collection, organization=None))
        response = client.post(endpoint("collections"), collection_dict)
        assert response.status_code == 201

        # Check that a creation attempt is blocked if a specified organization
        # is inaccessible to the requesting user.
        collection_dict = model_to_dict(baker.prepare(Collection, organization=None))
        collection_dict["organization"] = endpoint(
            "organizations", other_organization.id
        )
        response = client.post(endpoint("collections"), collection_dict)
        assert response.status_code == 403


@mark.django_db
def test_collections_endpoint_create_with_hyperlinked_related_variations(
    monkeypatch, user
):
    """Test creating a collecting using a variety of different absolute and relative
    hyperlinked organization URL formats."""
    client = AuthenticatedClient(user)

    # Get the default organization path in the format "/api/organizations/<id>"
    org_path = endpoint("organizations", user.organization.id)

    for org_path_prefix, script_name in (
        ("", None),
        ("http://localhost", None),
        ("https://localhost", None),
        ("http://localhost:8080", None),
        ("http://localhost/vault", "/vault/"),
        ("https://localhost/vault", "/vault/"),
        ("http://localhost:8080/vault", "/vault/"),
    ):
        collection_dict = model_to_dict(baker.prepare(Collection, organization=None))
        collection_dict["organization"] = org_path_prefix + org_path

        get_script_prefix = lambda: script_name or "/"
        # Patch get_script_prefix() in both our code and rest_framework.
        monkeypatch.setattr(vault.rest_api, "get_script_prefix", get_script_prefix)
        monkeypatch.setattr(
            rest_framework.relations, "get_script_prefix", get_script_prefix
        )
        response = client.post(endpoint("collections"), collection_dict)
        assert response.status_code == 201


@mark.django_db
def test_collections_endpoint_partial_update_allowed(users, make_collection, make_user):
    """Test that the collections endpoint does not updates on specific fields."""
    assert CollectionViewSet.mutable_fields == (
        "name",
        "fixity_frequency",
        "target_replication",
    )

    IMMUTABLE_FIELDS = {f.name for f in Collection._meta.fields}.difference(
        CollectionViewSet.mutable_fields
    )

    def assert_status(client, id, data, status):
        response = client.patch(endpoint("collections", id), data)
        assert response.status_code == status

    other_user = make_user()
    for user in users:
        # Make a user organization collection.
        collection = make_collection(
            organization=user.organization, fixity_frequency="QUARTERLY"
        )

        # Test that updates to "name", "fixity_frequency", and "target_replication" are
        # allowed.
        client = AuthenticatedClient(user)
        new_values_dict = {
            "name": f"{collection.name[:-4]}-new",
            "fixity_frequency": "MONTHLY",
            "target_replication": collection.target_replication + 1,
        }
        assert_status(
            client,
            collection.id,
            new_values_dict,
            200,
        )
        # Verify that the DB was actually updated.
        collection.refresh_from_db()
        assert collection.name == new_values_dict["name"]
        assert collection.fixity_frequency == new_values_dict["fixity_frequency"]
        assert collection.target_replication == new_values_dict["target_replication"]

        # Test that attempting to update any immutable field results in a 403.
        for field in IMMUTABLE_FIELDS:
            value = getattr(collection, field)
            # Replace Model-type field values with their URLs.
            if field in ("organization", "tree_node"):
                value = endpoint(f"{field.replace('_', '')}s", value.id)
            assert_status(client, collection.id, {field: value}, 403)


@mark.django_db
def test_collections_endpoint_saves_target_geolocations(make_user):
    user = make_user()
    client = AuthenticatedClient(user)
    org_id = user.organization_id
    assert len(Collection.objects.filter(organization_id=org_id)) == 0

    collection_dict = model_to_dict(baker.prepare(Collection, organization=None))
    response = client.post(endpoint("collections"), collection_dict)
    assert response.status_code == 201
    response_geolocations = sorted(
        [geo["name"] for geo in response.data["target_geolocations"]]
    )
    collection = Collection.objects.get(organization_id=org_id)
    geolocations = list(
        collection.target_geolocations.all()
        .order_by("name")
        .values_list("name", flat=True)
    )
    expected_geolocations = list(
        user.organization.plan.default_geolocations.all()
        .order_by("name")
        .values_list("name", flat=True)
    )
    assert geolocations == expected_geolocations
    assert response_geolocations == expected_geolocations


#### Geolocations Endpoint Tests ####


@mark.django_db
def test_geolocations_endpoint_retrieval_access(user, make_geolocation):
    """Test that the geolocations endpoint supports retrieval."""
    # Create a geolocation and retrieve it from the API.
    geolocation = model_to_dict(make_geolocation())
    client = AuthenticatedClient(user)
    response = client.get(endpoint("geolocations", geolocation["id"])).json()
    # Check that the geolocation field values are as expected.
    geolocation_id = geolocation.pop("id")
    response_url = response.pop("url")
    assert response == geolocation
    assert_hyperlinked_url(response_url, "geolocations", geolocation_id)


@mark.django_db
def test_geolocations_endpoint_list_access(user, make_geolocation):
    """Test that the geolocations endpoint supports list access."""
    geolocation = model_to_dict(make_geolocation())
    client = AuthenticatedClient(user)
    response = client.get(endpoint("geolocations"), size=-1).json()
    # Check that at least 1 geolocation was returned.
    assert response["count"] >= 1
    # Check that the geolocation we created is among the results, allowing
    # StopIteration to be raised if not.
    response_geo = next(
        x for x in response["results"] if x["name"] == geolocation["name"]
    )
    # Check that the geolocation field values are as expected.
    geolocation_id = geolocation.pop("id")
    response_url = response_geo.pop("url")
    assert response_geo == geolocation
    assert_hyperlinked_url(response_url, "geolocations", geolocation_id)


@mark.django_db
def test_geolocations_endpoint_mutation_not_allowed(users):
    """Test that the geolocations endpoint does not support creation or updates."""
    for user in users:
        client = AuthenticatedClient(user)
        for method in ("put", "post", "patch", "delete"):
            response = getattr(client, method)(endpoint("geolocations"), {})
            assert response.status_code == 405


#### Organizations Endpoint Tests ####


@mark.django_db
def test_organizations_endpoint_retrieval_access(make_user, users):
    """Test that a user can retrieve its own organization but not that of others."""
    # Create a new user and test retrieving its organization object.
    user = make_user()
    client = AuthenticatedClient(user)
    user_org_endpoint = endpoint("organizations", user.organization_id)
    org = client.get(user_org_endpoint).json()
    assert_hyperlinked_url(org["url"], "organizations", user.organization_id)
    # Assert that no other user is allowed to retrieve this organization object.
    for other_user in users:
        assert_404(AuthenticatedClient(other_user).get(user_org_endpoint))


@mark.django_db
def test_organizations_endpoint_list_access(users):
    """Test that each user can only access their own organization."""
    for user in users:
        client = AuthenticatedClient(user)
        response = client.get(endpoint("organizations")).json()
        assert response["count"] == 1
        assert_hyperlinked_url(
            response["results"][0]["url"], "organizations", user.organization.id
        )


@mark.django_db
def test_organizations_endpoint_list_html_filters(users):
    """Test that dropdowns in the organizations endpoint HTML response Filters dialog
    form contain only authorized values.
    """
    for user in users:
        selects = get_endpoint_html_filter_selects(user, "organizations")
        # Assert that there's a single plan select.
        assert len(selects) == 1
        assert selects[0].name == "plan"
        options = selects[0].getchildren()
        # Assert that the options comprise an initial placeholder and the single
        # user plan node.
        assert len(options) == 2
        assert_option_element_is_initial_empty_placeholder(options[0])
        assert int(options[1].get("value")) == user.organization.plan.id


@mark.django_db
def test_organizations_endpoint_mutation_not_allowed(users):
    """Test that the organizations endpoint does not support creation or updates."""
    for user in users:
        client = AuthenticatedClient(user)
        for method in ("put", "post", "patch", "delete"):
            response = getattr(client, method)(endpoint("organizations"), {})
            assert response.status_code == 405


#### Plans Endpoint Tests ####


@mark.django_db
def test_plans_endpoint_retrieval_access(make_user, users):
    """Test that a user can retrieve its own organization's plan but not that of
    others."""
    # Create a new user and test retrieving its organization's plan object.
    user = make_user()
    client = AuthenticatedClient(user)
    plan_endpoint = endpoint("plans", user.organization.plan_id)
    plan = client.get(plan_endpoint).json()
    assert_hyperlinked_url(plan["url"], "plans", user.organization.plan_id)
    # Assert that no other user is allowed to retrieve this plan object.
    for other_user in users:
        assert_404(AuthenticatedClient(other_user).get(plan_endpoint))


@mark.django_db
def test_plans_endpoint_list_access(users):
    """Assert that each user can only access plans associated with their organization."""
    for user in users:
        client = AuthenticatedClient(user)
        response = client.get(endpoint("plans")).json()
        assert response["count"] == 1
        assert_hyperlinked_url(
            response["results"][0]["url"], "plans", user.organization.plan.id
        )


@mark.django_db
def test_plans_endpoint_list_html_filters(users):
    """Test that dropdowns in the plans endpoint HTML response Filters dialog
    form contain only authorized values.
    """
    for user in users:
        selects = get_endpoint_html_filter_selects(user, "plans")
        # Assert that there are default_replication and default_fixity_frequency
        # selects.
        assert len(selects) == 2
        assert {x.name for x in selects} == {
            "default_replication",
            "default_fixity_frequency",
        }
        # These option values are non-sensitive so no need to check them.


@mark.django_db
def test_plans_endpoint_mutation_not_allowed(users):
    """Test that the plans endpoint does not support creation or updates."""
    for user in users:
        client = AuthenticatedClient(user)
        for method in ("put", "post", "patch", "delete"):
            response = getattr(client, method)(endpoint("plans"), {})
            assert response.status_code == 405


#### Users Endpoint Tests ####


@mark.django_db
def test_users_endpoint_retrieval_access(make_user, users):
    """Test that a user can retrieve its own user object but not that of others."""
    # Create a new user and test retrieving its user object.
    user = make_user()
    client = AuthenticatedClient(user)
    user_endpoint = endpoint("users", user.id)
    _user = client.get(user_endpoint).json()
    assert_hyperlinked_url(_user["url"], "users", user.id)
    # Assert that no other user is allowed to retrieve this user object.
    for other_user in users:
        assert_404(AuthenticatedClient(other_user).get(user_endpoint))


@mark.django_db
def test_users_endpoint_list_access(users):
    """Test that each user can only access their own user object."""
    for user in users:
        client = AuthenticatedClient(user)
        response = client.get(endpoint("users")).json()
        assert response["count"] == 1
        assert_hyperlinked_url(response["results"][0]["url"], "users", user.id)


@mark.django_db
def test_users_endpoint_list_html_filters(users):
    """Test that dropdowns in the users endpoint HTML response Filters dialog form
    contain only authorized values.
    """
    for user in users:
        selects = get_endpoint_html_filter_selects(user, "users")
        # Assert that there's a single organization select.
        assert len(selects) == 1
        assert selects[0].name == "organization"
        options = selects[0].getchildren()
        # Assert that the options comprise an initial placeholder and the single
        # user organization node.
        assert len(options) == 2
        assert_option_element_is_initial_empty_placeholder(options[0])
        assert int(options[1].get("value")) == user.organization.id


@mark.django_db
def test_users_endpoint_mutation_not_allowed(users):
    """Test that the users endpoint does not support creation or updates."""
    for user in users:
        client = AuthenticatedClient(user)
        for method in ("put", "post", "patch", "delete"):
            response = getattr(client, method)(endpoint("users"), {})
            assert response.status_code == 405


#### TreeNode Endpoint Tests ####


@mark.django_db
def test_treenodes_endpoint_retrieval_access(make_user, users, make_treenode):
    """Test that a user can retrieve its own treenode objects but not those of others."""
    # Create a new user and test retrieving its organization tree_node object.
    user = make_user()
    client = AuthenticatedClient(user)

    # Add some more depth to this user's tree.
    treenodes = [user.organization.tree_node]
    for node_type in ("COLLECTION", "FOLDER", "FILE"):
        treenodes.append(make_treenode(parent=treenodes[-1], node_type=node_type))

    # Test that the user can retrieve all nodes.
    for treenode in treenodes:
        _treenode = client.get(endpoint("treenodes", treenode.id)).json()
        assert_hyperlinked_url(_treenode["url"], "treenodes", treenode.id)

    # Assert that no other user is allowed to retrieve any of the user's nodes.
    for other_user in users:
        other_client = AuthenticatedClient(other_user)
        for treenode in treenodes:
            assert_404(other_client.get(endpoint("treenodes", treenode.id)))


@mark.django_db
def test_treenodes_endpoint_list_access(users, make_treenode):
    """Test that each user can only access treenodes that are descendents of
    their organization treenode."""
    # Add a COLLECTION-type node to each user's organization node.
    for user in users:
        make_treenode(parent=user.organization.tree_node, node_type="COLLECTION")

    # Instantiate an AuthenticatedClient for each user.
    clients = [AuthenticatedClient(user) for user in users]

    # Test retrieving all organization nodes order by ID ascending.
    for client in clients:
        response = client.get(endpoint("treenodes"), {"ordering": "id"}).json()
        assert response["count"] == 2
        assert_hyperlinked_url(
            response["results"][0]["url"],
            "treenodes",
            client.user.organization.tree_node.id,
        )
        assert response["results"][0]["node_type"] == "ORGANIZATION"
        assert response["results"][1]["node_type"] == "COLLECTION"

    # Test querying descendent nodes by specifying node_type=COLLECTION.
    for client in clients:
        response = client.get(endpoint("treenodes"), {"node_type": "COLLECTION"}).json()
        assert response["count"] == 1
        assert response["results"][0]["node_type"] == "COLLECTION"
        assert_hyperlinked_url(
            response["results"][0]["parent"],
            "treenodes",
            client.user.organization.tree_node_id,
        )


@mark.django_db
def test_treenodes_endpoint_list_html_filters(users):
    """Test that dropdowns in the treenodes endpoint HTML response Filters dialog
    form contain only authorized values.
    """
    for user in users:
        selects = get_endpoint_html_filter_selects(user, "treenodes")
        # Assert that there are node_type and uploaded_by selects.
        name_select_map = {x.name: x for x in selects}
        assert set(name_select_map) == {"node_type", "uploaded_by"}
        # Check that non-placeholder uploaded_by options comprise the single
        # requesting user.
        options = name_select_map["uploaded_by"].getchildren()
        assert_option_element_is_initial_empty_placeholder(options[0])
        assert int(options[1].get("value")) == user.id


@mark.django_db
def test_treenode_endpoint_create_only_folder_allowed(users, make_treenode, make_user):
    """Test that the treenodes endpoint only allows FOLDER creation."""
    NON_FOLDER_TYPES = [x for x, _ in TreeNode.Type.choices if x != "FOLDER"]

    # Create a unique user and collection node to serve as unauthorized parent.
    other_user = make_user()
    other_collection_node = make_treenode(
        node_type="COLLECTION", parent=other_user.organization.tree_node
    )
    other_collection_node_path = endpoint("treenodes", other_collection_node.id)

    for user in users:
        client = AuthenticatedClient(user)

        # Create a user organization COLLECTION-type node to serve as a parent.
        collection_node = make_treenode(
            node_type="COLLECTION", parent=user.organization.tree_node
        )
        collection_node_path = endpoint("treenodes", collection_node.id)

        treenode_dict = {
            k: v
            for k, v in model_to_dict(baker.prepare(TreeNode, parent=None)).items()
            if v is not None and k != "id"
        }
        # Set parent as the URL of the collection treenode instance.
        treenode_dict["parent"] = collection_node_path

        # Check that FOLDER-type creation is allowed.
        treenode_dict["node_type"] = "FOLDER"
        response = client.post(endpoint("treenodes"), treenode_dict)
        assert response.status_code == 201

        # Check that non-FOLDER-type creation attempts are blocked.
        for node_type in NON_FOLDER_TYPES:
            treenode_dict["node_type"] = node_type
            response = client.post(endpoint("treenodes"), treenode_dict)
            assert response.status_code == 400

        # Check that a creation attempt with an unauthorized parent is blocked.
        treenode_dict["node_type"] = "FOLDER"
        treenode_dict["parent"] = other_collection_node_path
        response = client.post(endpoint("treenodes"), treenode_dict)
        assert response.status_code == 403


@mark.django_db
def test_treenode_endpoint_partial_update_allowed(
    users, make_collection, make_treenode, make_user
):
    """Test that the treenodes endpoint does not updates on specific fields."""
    assert TreeNodeViewSet.mutable_fields == ("name", "parent")

    IMMUTABLE_FIELDS = {f.name for f in TreeNode._meta.fields}.difference(
        TreeNodeViewSet.mutable_fields
    )

    def assert_status(client, id, data, status):
        response = client.patch(endpoint("treenodes", id), data)
        assert response.status_code == status

    other_user = make_user()
    for user in users:
        # Make two FOLDER-type tree nodes as direct descendants of a collection that
        # belongs to the user's organization.
        collection = make_collection(
            parent_node=user.organization.tree_node,
            organization=user.organization,
        )
        treenode1 = make_treenode(parent=collection.tree_node, node_type="FOLDER")
        treenode2 = make_treenode(parent=collection.tree_node, node_type="FOLDER")

        # Test that updates to "name" and "parent" are allowed.
        client = AuthenticatedClient(user)
        # Create a non-persisted TreeNode instance to serve as field value factory.
        mock_treenode = baker.prepare(TreeNode)
        # Update treenode2's name and make it a child of treenode1.
        # Note that the "parent" value needs to be a URL.
        assert_status(
            client,
            treenode2.id,
            {"name": mock_treenode.name, "parent": endpoint("treenodes", treenode1.id)},
            200,
        )
        # Verify that the DB was actually updated.
        treenode2.refresh_from_db()
        assert treenode2.name == mock_treenode.name
        assert treenode2.parent.id == treenode1.id

        # Check that the specified parent must be a descendant of the user's org.
        assert_status(
            client,
            treenode2.id,
            {"parent": endpoint("treenodes", other_user.organization.id)},
            403,
        )

        # Test that attempting to update any immutable field results in a 403.
        for field in IMMUTABLE_FIELDS:
            assert_status(
                client, treenode2.id, {field: getattr(mock_treenode, field)}, 403
            )


@mark.django_db
def test_treenodes_delete__success(make_user, users, make_treenode):
    """DELETE treenodes/:id basic correctness"""
    # Given: a folder treenode
    user = make_user()
    client = AuthenticatedClient(user)
    treenodes = [user.organization.tree_node]
    for node_type in ("COLLECTION", "FOLDER", "FILE"):
        treenodes.append(make_treenode(parent=treenodes[-1], node_type=node_type))
    folder_node = treenodes[2]
    file_node = treenodes[3]

    # When: DELETE
    response = client.delete(endpoint("treenodes", folder_node.id))

    # Then: the folder node and its children are deleted
    folder_node.refresh_from_db()
    file_node.refresh_from_db()
    assert response.status_code == 200
    assert folder_node.deleted
    assert file_node.deleted


@mark.django_db
def test_treenodes_delete__already_deleted(make_user, users, make_treenode):
    """DELETE treenodes/:id returns 404 on already soft-deleted treenodes"""
    # Given: a soft-deleted folder subtree
    user = make_user()
    client = AuthenticatedClient(user)
    treenodes = [user.organization.tree_node]
    for node_type in ("COLLECTION", "FOLDER", "FILE"):
        treenodes.append(make_treenode(parent=treenodes[-1], node_type=node_type))
    folder_node = treenodes[2]
    file_node = treenodes[3]

    folder_node.refresh_from_db()
    folder_node.delete()

    folder_node.refresh_from_db()
    file_node.refresh_from_db()
    assert folder_node.deleted
    assert file_node.deleted

    # When: DELETE
    response = client.delete(endpoint("treenodes", folder_node.id))

    # Then: the folder node and its children are deleted
    folder_node.refresh_from_db()
    file_node.refresh_from_db()
    assert response.status_code == 404
    assert folder_node.deleted
    assert file_node.deleted


@mark.django_db
def test_treenodes_delete__undeletable_node_types(make_user, users, make_treenode):
    """DELETE treenodes/:id returns bad request on undeletable node types"""
    # Given: a collection treenode
    user = make_user()
    client = AuthenticatedClient(user)
    treenodes = [user.organization.tree_node]
    for node_type in ("COLLECTION", "FOLDER", "FILE"):
        treenodes.append(make_treenode(parent=treenodes[-1], node_type=node_type))
    collection_node = treenodes[1]

    # When: DELETE
    response = client.delete(endpoint("treenodes", collection_node.id))

    # Then: bad request
    collection_node.refresh_from_db()
    assert response.status_code == 400
    assert response.data == "unable to delete TreeNode of type COLLECTION"
    assert collection_node.deleted is False


#### retrieve endpoint __depth param tests ####


def _test__depth_param_on_retrieve_endpoint(
    user, child_node, __depth, parent_field_type
):
    """test__depth _param_*_on_retrieve_endpoint test helper."""
    client = AuthenticatedClient(user)
    response = client.get(
        endpoint("treenodes", child_node.id),
        {"__depth": __depth} if __depth is not None else None,
    ).json()
    assert isinstance(response["parent"], parent_field_type)


@mark.django_db
def test__depth_param_unspecified_on_retrieve_endpoint(user_and_child_node):
    """Test that expansion does not happen when__depth is unspecified."""
    user, child_node = user_and_child_node
    _test__depth_param_on_retrieve_endpoint(user, child_node, None, str)


@mark.django_db
def test__depth_param_eq_0_on_retrieve_endpoint(user_and_child_node):
    # Check that parent is not expanded when __depth=0 is specified.
    user, child_node = user_and_child_node
    _test__depth_param_on_retrieve_endpoint(user, child_node, 0, str)


@mark.django_db
def test__depth_param_eq_1_on_retrieve_endpoint(user_and_child_node):
    # Check that parent is expanded when __depth=1 is specified.
    user, child_node = user_and_child_node
    _test__depth_param_on_retrieve_endpoint(user, child_node, 1, dict)


#### list endpoint __depth param tests ####


def _test__depth_param_on_list_endpoint(user, child_node, __depth, parent_field_type):
    """test__depth _param_*_on_list_endpoint test helper."""
    client = AuthenticatedClient(user)
    params = {"id": child_node.id}
    if __depth is not None:
        params["__depth"] = __depth
    response = client.get(endpoint("treenodes"), params).json()
    assert response["count"] == 1
    assert isinstance(response["results"][0]["parent"], parent_field_type)


@mark.django_db
def test__depth_param_unspecified_on_list_endpoint(user_and_child_node):
    """Test that expansion does not happen when__depth is unspecified."""
    user, child_node = user_and_child_node
    _test__depth_param_on_list_endpoint(user, child_node, None, str)


@mark.django_db
def test__depth_param_eq_0_on_list_endpoint(user_and_child_node):
    # Check that parent is not expanded when __depth=0 is specified.
    user, child_node = user_and_child_node
    _test__depth_param_on_retrieve_endpoint(user, child_node, 0, str)


@mark.django_db
def test__depth_param_eq_1_on_list_endpoint(user_and_child_node):
    # Check that parent is expanded when __depth=1 is specified.
    user, child_node = user_and_child_node
    _test__depth_param_on_retrieve_endpoint(user, child_node, 1, dict)
