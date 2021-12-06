import pytest

from tests.vault.fixtures import super_user
from vault.management.commands.add_treenodes_for_org import add_treenodes_for_org
from vault.models import Collection, Organization, TreeNode


@pytest.fixture
def no_node_org(db, super_user) -> Organization:
    org = super_user.organization
    collection = Collection.objects.create(
        name="Test Collection",
        organization=org,
    )
    collection_node = collection.tree_node
    collection.tree_node = None
    collection.save()
    collection_node.delete()
    org_node = org.tree_node
    org.tree_node = None
    org.save()
    org_node.delete()

    return org


@pytest.fixture
def orphan_node_org(db, super_user) -> Organization:
    org = super_user.organization
    collection = Collection.objects.create(
        name="Test Collection",
        organization=org,
    )
    collection.tree_node = None
    collection.save()
    org.tree_node = None
    org.save()

    return org


@pytest.mark.django_db
def test_no_node_org_has_no_nodes(no_node_org):
    assert len(TreeNode.objects.all()) == 0
    assert no_node_org.tree_node is None
    collection = Collection.objects.get(organization=no_node_org)
    assert collection.tree_node is None


@pytest.mark.django_db
def test_orphan_node_org_has_orphaned_nodes(orphan_node_org):
    assert len(TreeNode.objects.all()) == 2
    assert orphan_node_org.tree_node is None
    collection = Collection.objects.get(organization=orphan_node_org)
    assert collection.tree_node is None


@pytest.fixture
def org(request) -> Organization:
    return request.getfixturevalue(request.param)


@pytest.mark.django_db
@pytest.mark.parametrize("org", ["no_node_org", "orphan_node_org"], indirect=True)
def test_add_treenodes_for_org(org: Organization):
    add_treenodes_for_org(org)
    assert len(TreeNode.objects.all()) == 2
    assert org.tree_node is not None
    collection = Collection.objects.get(organization=org)
    assert collection.tree_node is not None
