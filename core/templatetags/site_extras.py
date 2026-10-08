from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """{{ mapping|get_item:key }} for a key held in a variable."""
    try:
        return mapping.get(key, [])
    except AttributeError:
        return []
