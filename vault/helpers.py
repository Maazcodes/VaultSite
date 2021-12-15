from decimal import Decimal


def safe_number_parser(type_func):
    """Return the result of parsing a string as an number with optional
    _min/_max constraints. Return the value of default if parsing fails or
    a constraint is violated.
    """

    def f(s, default=None, _min=None, _max=None):
        try:
            n = type_func(s)
        except (TypeError, ValueError):
            return default
        if (_min is not None and n < _min) or (_max is not None and n > _max):
            return default
        return n

    return f


safe_parse_int = safe_number_parser(int)
safe_parse_float = safe_number_parser(float)
safe_parse_decimal = safe_number_parser(Decimal)
