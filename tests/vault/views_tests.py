from model_bakery import baker
import pytest

from vault import views
from vault.models import Collection, Organization, Report, TreeNode


@pytest.mark.django_db
def test_deposit_report(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])
    collection = baker.make("Collection", organization=user.organization)
    deposit = baker.make(
        "Deposit", user=user, organization=user.organization, collection=collection
    )
    files = baker.make("DepositFile", deposit=deposit, _quantity=5)
    request = rf.get(f"/deposit/{deposit.id}")
    request.user = user
    response = views.deposit_report(request, deposit.id)
    assert response.status_code == 200


@pytest.mark.django_db
def test_collection(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])
    collection = baker.make("Collection", organization=user.organization)
    deposit = baker.make(
        "Deposit", user=user, organization=user.organization, collection=collection
    )
    files = baker.make("DepositFile", deposit=deposit, _quantity=5)
    old_deposit_report = baker.make(
        "Report", collection=collection, report_type=Report.ReportType.DEPOSIT
    )
    fixity_report = baker.make(
        "Report", collection=collection, report_type=Report.ReportType.FIXITY
    )
    assert len(Organization.objects.all()) == 1
    assert len(Collection.objects.all()) == 1
    assert len(TreeNode.objects.all()) == 2

    request = rf.get(f"/collection/{collection.id}")
    request.user = user
    response = views.collection(request, collection.id)
    assert response.status_code == 200
