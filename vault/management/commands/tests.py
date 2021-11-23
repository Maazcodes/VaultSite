import pytest
from django.db.models import Max

from django.utils import timezone

from vault.models import Collection, Deposit, DepositFile, TreeNode
from vault.tests import super_user
from vault.management.commands.add_treenodes_for_org import add_treenodes_for_org
from vault.management.commands.fix_deposit_timestamps_for_org import (
    fix_deposit_timestamps_for_org,
)


@pytest.fixture
def no_node_org(db, super_user):
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
def orphan_node_org(db, super_user):
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


def test_no_node_org_has_no_nodes(db, no_node_org):
    assert len(TreeNode.objects.all()) == 0
    assert no_node_org.tree_node is None
    collection = Collection.objects.get(organization=no_node_org)
    assert collection.tree_node is None


def test_orphan_node_org_has_orphaned_nodes(db, orphan_node_org):
    assert len(TreeNode.objects.all()) == 2
    assert orphan_node_org.tree_node is None
    collection = Collection.objects.get(organization=orphan_node_org)
    assert collection.tree_node is None


@pytest.fixture
def org(request):
    return request.getfixturevalue(request.param)


@pytest.mark.parametrize("org", ["no_node_org", "orphan_node_org"], indirect=True)
def test_add_treenodes_for_org(db, org):
    add_treenodes_for_org(org)
    assert len(TreeNode.objects.all()) == 2
    assert org.tree_node is not None
    collection = Collection.objects.get(organization=org)
    assert collection.tree_node is not None


def test_calculate_hashed_at(db, super_user):
    org = super_user.organization
    coll = Collection.objects.create(name="Test Collection", organization=org)
    deposit = Deposit.objects.create(
        organization=org,
        collection=coll,
        user=super_user,
        state=Deposit.State.HASHED,
    )
    expected_time = timezone.now()
    for i in range(3):
        deposit_file = DepositFile.objects.create(
            deposit=deposit,
            flow_identifier=str(i),
            name=str(i),
            relative_path=str(i),
            size=100,
            state=DepositFile.State.HASHED,
            registered_at=expected_time,
            # leave uploaded_at blank to test max NULL
            hashed_at=expected_time,
        )
    fix_deposit_timestamps_for_org(org)
    deposit = Deposit.objects.get(collection=coll)
    assert deposit.uploaded_at is None
    assert deposit.hashed_at == expected_time
