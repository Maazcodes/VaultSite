from django.conf import settings
import pytest

from vault.models import User


@pytest.mark.django_db
def test_my_user(super_user):
    me = User.objects.get(username=settings.TEST_FIXTURE_USER)
    assert me.is_superuser
