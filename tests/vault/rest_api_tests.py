from pytest import (
    fixture,
    mark,
)

from rest_framework.test import APIClient


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
    child_node = make_treenode(parent=user.organization.tree_node)
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
        # Set the HTTP header required for Django RemoteUserBackend.
        self.credentials(REMOTE_USER=user.username)


def assert_404(response):
    """Assert a 404 status API response."""
    assert response.status_code == 404


def endpoint(resource_name, resource_id=None):
    """Return the API endpoint path for a specified resource."""
    assert resource_name in (
        "organizations",
        "plans",
        "treenodes",
        "users",
    )
    if resource_id is None:
        return f"/api/{resource_name}/"
    else:
        return f"/api/{resource_name}/{resource_id}/"


def assert_hyperlinked_url(url, resource_name, resource_id):
    """Assert that a HyperlinkedModelSerializer URL is as expected."""
    assert url.endswith(endpoint(resource_name, resource_id))


###############################################################################
# Tests
###############################################################################

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
