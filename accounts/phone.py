"""WhatsApp number handling: validation for the forms and the international digits wa.me needs."""
import re

from django.conf import settings
from django.core.exceptions import ValidationError

INVALID = "أدخل رقم واتس اب صحيحًا (مثال: 01012345678) / Enter a valid WhatsApp number."


def whatsapp_digits(value):
    """International digits for wa.me (no '+'), or None when the value is not a usable number.

    Accepts +20…, 0020…, a local number with a leading 0 (the default country code is added),
    and spaces, dashes or brackets between digits.
    """
    raw = (value or "").strip()
    if not raw or re.search(r"[^\d\s+\-().]", raw):
        return None
    digits = re.sub(r"\D", "", raw)
    country = getattr(settings, "WHATSAPP_DEFAULT_COUNTRY_CODE", "20")
    if raw.startswith("+"):
        pass
    elif digits.startswith("00"):
        digits = digits[2:]
    elif digits.startswith("0"):
        digits = country + digits[1:]
    elif not digits.startswith(country) and len(digits) <= 10:
        digits = country + digits
    return digits if 8 <= len(digits) <= 15 else None


def validate_whatsapp(value):
    if whatsapp_digits(value) is None:
        raise ValidationError(INVALID)
    return value.strip()
