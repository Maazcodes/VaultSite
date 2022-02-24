from rest_framework.authentication import RemoteUserAuthentication


class VaultRemoteUserAuthentication(RemoteUserAuthentication):
    """
    RemoteUserAuthentication subclass which reads a different header. This is
    necessary because all headers set by an upstream HTTP server (e.g.,
    nginx) get prefixed with `HTTP_` by django. Because the default header
    name is `REMOTE_USER` (a header only writeable by an upstream WSGI
    server), we must read a different header name.
    """

    header = "HTTP_REMOTE_USER"
