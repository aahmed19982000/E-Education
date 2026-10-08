from django import template

from accounts.phone import whatsapp_digits

register = template.Library()


@register.filter
def whatsapp_url(phone):
    """https://wa.me/<international digits>, or '' when the phone is not a usable number."""
    digits = whatsapp_digits(phone)
    return f"https://wa.me/{digits}" if digits else ""


@register.inclusion_tag("dashboard/_whatsapp_link.html")
def whatsapp_link(phone):
    """A 'send a WhatsApp message' link that opens WhatsApp for this number (nothing if it has none)."""
    return {"url": whatsapp_url(phone)}
