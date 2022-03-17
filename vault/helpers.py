from decimal import Decimal


def _safe_number_parser(type_func):
    """Return the result of parsing a string as an number with optional
    _min/_max constraints. Return the value of default if parsing fails or
    a constraint is violated.
    """

    def func(to_parse, default=None, _min=None, _max=None):
        try:
            num = type_func(to_parse)
        except (TypeError, ValueError):
            return default
        if (_min is not None and num < _min) or (_max is not None and num > _max):
            return default
        return num

    return func


safe_parse_int = _safe_number_parser(int)
safe_parse_float = _safe_number_parser(float)
safe_parse_decimal = _safe_number_parser(Decimal)
