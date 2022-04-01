from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login

from basicauth.basicauthutils import extract_basicauth
from basicauth.response import HttpResponseUnauthorized


def _authenticate_request(request) -> bool:
    """Verify and authenticate app User via basicauth headers

    Returns:
        - True if authentication passed
        - authenticates user

    This function is a customized version of the one in django-basicauth
    """
    if getattr(settings, "BASICAUTH_DISABLE", False):
        # Not to use this env
        return True

    if "HTTP_AUTHORIZATION" not in request.META:
        return False

    authorization_header = request.META["HTTP_AUTHORIZATION"]
    ret = extract_basicauth(authorization_header)
    if not ret:
        return False

    username, password = ret

    user = authenticate(username=username, password=password)
    if user is not None:
        login(request, user)
        return True

    return False


def basic_auth_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_anonymous and not _authenticate_request(request):
            return HttpResponseUnauthorized()
        return view_func(request, *args, **kwargs)

    return _wrapped
