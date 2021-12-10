import pytest

from django.conf import settings

from vault.models import User, Organization, Plan, Geolocation


@pytest.fixture
def geolocation():
    return Geolocation.objects.create(name="Test Geo")


@pytest.fixture
def plan(geolocation):
    plan = Plan.objects.create(name="Test Plan", price_per_terabyte=0)
    plan.default_geolocations.set([geolocation])
    return plan


@pytest.fixture
def organization(plan):
    return Organization.objects.create(name="Test Org", plan=plan)


@pytest.fixture
def super_user(organization):
    return User.objects.create_superuser(
        username=settings.TEST_FIXTURE_USER,
        password="test1234",
        organization=organization
    )
