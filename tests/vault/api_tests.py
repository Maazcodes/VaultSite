import json

from django.urls import reverse
from model_bakery import baker
import pytest

from vault import api
from vault.models import Collection, Organization, Report, TreeNode


@pytest.mark.django_db
@pytest.mark.parametrize("coll_count", [0, 3])
def test_api_collections(rf, coll_count):
    user = baker.make("vault.User", _fill_optional=["organization"])
    if coll_count > 0:
        baker.make("Collection", organization=user.organization, _quantity=coll_count)
    assert len(Organization.objects.all()) == 1
    assert len(Collection.objects.all()) == coll_count

    request = rf.get(reverse("api_collections"))
    request.user = user
    response = api.collections(request)
    assert response.status_code == 200
    colls = json.loads(response.content)["collections"]
    assert len(colls) == coll_count


@pytest.mark.django_db
def test_api_reports(rf):
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

    request = rf.get(f"/api/reports")
    request.user = user
    response = api.reports(request)
    assert response.status_code == 200
    reports = json.loads(response.content)["reports"]
    assert len(reports) == 3
