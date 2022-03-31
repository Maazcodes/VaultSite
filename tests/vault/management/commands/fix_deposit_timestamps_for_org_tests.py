from django.utils import timezone
import pytest

from vault.models import Collection, Deposit, DepositFile
from vault.management.commands.fix_deposit_timestamps_for_org import (
    fix_deposit_timestamps_for_org,
)


@pytest.mark.django_db
def test_calculate_hashed_at(super_user):
    org = super_user.organization
    coll = Collection.objects.create(name="Test Collection", organization=org)
    deposit = Deposit.objects.create(
        organization=org,
        collection=coll,
        user=super_user,
        state=Deposit.State.HASHED,
        parent_node_id=coll.tree_node.id,
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
