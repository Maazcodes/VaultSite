from django.conf import settings
import pytest

from tests.vault.fixtures import super_user
from vault.models import User


@pytest.mark.django_db
def test_my_user(super_user):
    me = User.objects.get(username=settings.TEST_FIXTURE_USER)
    assert me.is_superuser
