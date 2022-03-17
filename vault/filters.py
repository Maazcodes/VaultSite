from datetime import datetime
from json import JSONEncoder

from django.forms import model_to_dict
from django.db.models import (
    Model,
    QuerySet,
)


class ExtendedJSONEncoder(JSONEncoder):
    """JSONEncoder subclass that can handle additional types."""

    def default(self, o):
        if isinstance(o, Model):
            return model_to_dict(o)

        if isinstance(o, QuerySet):
            # Return a QuerySet as a list of dicts.
            return list(o.values())

        if isinstance(o, datetime):
            # Encode datetimes as an ISO-8601 string.
            return o.isoformat()

        return super().default(o)


tojson2 = ExtendedJSONEncoder(separators=(",", ":")).encode


# TODO - maybe make this work for Django templates.
# Currently it complains about:
# AttributeError: 'method' object has no attribute '_filter_name'
#
# from django import template
# register = template.Library()
# register.filter('tojson2', tojson2)
