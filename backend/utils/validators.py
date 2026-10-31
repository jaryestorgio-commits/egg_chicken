import re
from decimal import Decimal, InvalidOperation


EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def request_data(request):
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None


def required_string(data, field, *, max_length=300):
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        return None, f"{field} is required"
    value = value.strip()
    if len(value) > max_length:
        return None, f"{field} must be at most {max_length} characters"
    return value, None


def parse_positive_int(value, field, *, allow_zero=False):
    if isinstance(value, bool):
        return None, f"{field} must be an integer"
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, f"{field} must be an integer"
    if str(parsed) != str(value).strip() and not isinstance(value, int):
        return None, f"{field} must be an integer"
    if parsed < (0 if allow_zero else 1):
        return None, f"{field} must be {'zero or greater' if allow_zero else 'greater than zero'}"
    return parsed, None


def parse_money(value, field="price"):
    if isinstance(value, bool):
        return None, f"{field} must be a valid non-negative amount"
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None, f"{field} must be a valid non-negative amount"
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        return None, f"{field} must be a valid non-negative amount with at most 2 decimal places"
    return amount.quantize(Decimal("0.01")), None


def valid_email(email):
    return isinstance(email, str) and bool(EMAIL_PATTERN.fullmatch(email.strip()))