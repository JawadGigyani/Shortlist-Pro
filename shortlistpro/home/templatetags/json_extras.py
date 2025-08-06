import json
from django import template

register = template.Library()

@register.filter
def load_json(value):
    """Parse a JSON string into a Python object"""
    if not value:
        return {}
    try:
        if isinstance(value, str):
            return json.loads(value)
        return value
    except (json.JSONDecodeError, TypeError):
        return {}

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary"""
    if not dictionary or not isinstance(dictionary, dict):
        return None
    return dictionary.get(key)
