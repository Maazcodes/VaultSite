from django.templatetags.static import static
from django.urls import reverse

from jinja2 import Environment

from vault.filters import tojson2


def environment(**options):
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
        }
    )
    env.filters["tojson2"] = tojson2
    return env
