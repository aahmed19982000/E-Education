from django import template
from django.urls import reverse

from core.models import SiteSettings
from core.translations import get_translations

register = template.Library()


@register.filter
def get_item(mapping, key):
    """{{ mapping|get_item:key }} for a key held in a variable."""
    try:
        return mapping.get(key, [])
    except AttributeError:
        return []


@register.simple_tag(takes_context=True)
def price_inquiry_url(context, title=""):
    """Link for "ask for the price": WhatsApp chat with a ready message, or the contact page without a number."""
    lang = getattr(context.get("request"), "lang", "ar")
    text = get_translations(lang)["courses"]["askPriceMsg"].format(title=title).strip() if title else \
        get_translations(lang)["courses"]["askPriceMsgGeneral"]
    return SiteSettings.load().inquiry_url(text) or reverse("contact:contact")
