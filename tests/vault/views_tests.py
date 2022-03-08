from django.http import Http404
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
def test_fixity_report_auth(rf, make_fixity_report):
    """A user should only be able to see Reports from their own Organization."""
    # Make two reports for two different orgs with two users.
    report_1 = make_fixity_report()
    report_2 = make_fixity_report()
    org_1 = report_1.collection.organization
    org_2 = report_2.collection.organization
    user_1 = baker.make("vault.User", organization=org_1)
    user_2 = baker.make("vault.User", organization=org_2)

    # Test a user can see their own organization's report:
    request = rf.get(f"/reports/fixity/{report_1.id}")
    request.user = user_1
    response = views.fixity_report(request, report_1.id)
    assert response.status_code == 200

    # Test a user may not see a different organization's report.
    request = rf.get(f"/reports/fixity/{report_1.id}")
    request.user = user_2
    with pytest.raises(Http404):
        views.fixity_report(request, report_1.id)


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
