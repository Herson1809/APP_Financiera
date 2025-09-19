# apps/core/templatetags/dict_extras.py
from django import template

register = template.Library()

@register.filter
def get_item(d, key):
    """Devuelve d[key] si existe; si no, None."""
    try:
        return d.get(key)
    except Exception:
        return None

@register.filter
def get_subitem(d, subkey):
    """Devuelve d[subkey] para dicts anidados (ej. {'abs':1})."""
    try:
        return d.get(subkey)
    except Exception:
        return None
