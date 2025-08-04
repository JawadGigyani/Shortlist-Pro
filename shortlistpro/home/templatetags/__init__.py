from django import template
import json

register = template.Library()

@register.filter
def format_certifications(value):
    """Format certifications JSON for display"""
    if not value:
        return ''
    
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    if isinstance(value, list):
        formatted_certs = []
        for cert in value:
            if isinstance(cert, dict):
                name = cert.get('name', '')
                org = cert.get('issuing_organization', '')
                if name and org:
                    formatted_certs.append(f"{name} ({org})")
                elif name:
                    formatted_certs.append(name)
            elif cert:
                formatted_certs.append(str(cert))
        return ', '.join(formatted_certs)
    
    return str(value)
