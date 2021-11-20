import pytest

from django.conf import settings

from vault.models import User, Organization, Plan, Geolocation


@pytest.fixture
def super_user(db):
    geo = Geolocation.objects.create(name="Test Geo")
    plan = Plan.objects.create(name="Test Plan", price_per_terabyte=0)
    plan.default_geolocations.set([geo])
    org = Organization.objects.create(name="Test Org", plan=plan)
    su = User.objects.create_superuser(
        username=settings.TEST_FIXTURE_USER, password="test1234", organization=org
    )
    return su


def test_my_user(db, super_user):
    me = User.objects.get(username=settings.TEST_FIXTURE_USER)
    assert me.is_superuser
