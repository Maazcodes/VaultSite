from model_bakery import baker
import pytest

from vault import views


@pytest.mark.django_db
def test_deposit_report(rf):
    user = baker.make("vault.User", _fill_optional=["organization"])
    deposit = baker.make("Deposit", user=user, organization=user.organization)
    files = baker.make("DepositFile", deposit=deposit, _quantity=5)
    request = rf.get(f"/deposit/{deposit.id}")
    request.user = user
    response = views.deposit_report(request, deposit.id)
    assert response.status_code == 200
