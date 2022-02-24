from pytest import fixture

from django.conf import settings
from model_bakery import baker

from vault.models import (
    Collection,
    Geolocation,
    Organization,
    Plan,
    TreeNode,
    User,
)


###############################################################################
# Factory Fixtures
###############################################################################


@fixture
def make_collection():
    return lambda **kwargs: baker.make(Collection, **kwargs)


@fixture
def make_geolocation():
    return lambda **kwargs: baker.make(Geolocation, **kwargs)


@fixture
def make_plan(geolocation):
    def maker(**kwargs):
        plan = baker.make(Plan, price_per_terabyte=0, **kwargs)
        plan.default_geolocations.set([geolocation])
        plan.save()
        return plan

    return maker


@fixture
def make_treenode():
    def maker(parent, node_type="FILE", **kwargs):
        # Enforce valid-length default names for ORGANIZATION and COLLECTION-type node.
        model = {"ORGANIZATION": Organization, "COLLECTION": Collection}.get(node_type)
        if model and "name" not in kwargs:
            kwargs["name"] = baker.prepare(model).name
        return baker.make(TreeNode, parent=parent, node_type=node_type, **kwargs)

    return maker


@fixture
def make_organization(make_plan):
    def maker(**kwargs):
        if "plan" not in kwargs:
            kwargs["plan"] = make_plan()
        organization = baker.make(Organization, **kwargs)
        # Assert that a TreeNode is automatically created.
        assert isinstance(organization.tree_node, TreeNode)
        return organization

    return maker


@fixture
def make_super_user(make_organization):
    return lambda: baker.make(
        User, organization=make_organization(), is_staff=True, is_superuser=True
    )


@fixture
def make_staff_user(make_organization):
    return lambda: baker.make(User, organization=make_organization(), is_staff=True)


@fixture
def make_user(make_organization):
    def maker(organization=None):
        organization = organization or make_organization()
        return baker.make(User, organization=organization)

    return maker


###############################################################################
# Normal Fixtures
###############################################################################


@fixture
def geolocation(make_geolocation):
    return make_geolocation()


@fixture
def plan(make_plan):
    return make_plan()


@fixture
def organization(make_organization):
    return make_organization()


@fixture
def super_user(make_super_user):
    return make_super_user()


@fixture
def staff_user(make_staff_user):
    return make_staff_user()


@fixture
def user(make_user):
    return make_user()


@fixture
def treenode_stack(make_treenode, make_collection, make_organization):
    """Return a complete valid TreeNode type hierarchy dict keyed by type name."""
    organization = make_organization()
    organization.refresh_from_db()
    organization_node = organization.tree_node
    organization_node.refresh_from_db()
    collection = make_collection()
    collection.refresh_from_db()
    collection_node = collection.tree_node
    collection_node.refresh_from_db()
    folder_node = make_treenode(node_type="FOLDER", parent=collection_node)
    folder_node.refresh_from_db()
    file_node = make_treenode(node_type="FILE", parent=folder_node)
    file_node.refresh_from_db()
    return {
        "ORGANIZATION": organization_node,
        "COLLECTION": collection_node,
        "FOLDER": folder_node,
        "FILE": file_node,
    }
