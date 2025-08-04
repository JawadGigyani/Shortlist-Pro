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

@register.filter
def format_skills(value):
    """Format skills JSON for display"""
    if not value:
        return ''
    
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    if isinstance(value, list):
        return ', '.join([str(skill) for skill in value if skill])
    
    return str(value)

@register.filter
def format_education(value):
    """Format education JSON for display"""
    if not value:
        return ''
    
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    if isinstance(value, list):
        formatted_edu = []
        for edu in value:
            if isinstance(edu, dict):
                degree = edu.get('degree_title', '')
                institution = edu.get('institution_name', '')
                end_date = edu.get('end_date', '')
                
                edu_text = degree
                if institution:
                    edu_text += f" from {institution}"
                if end_date:
                    edu_text += f" ({end_date})"
                
                if edu_text.strip():
                    formatted_edu.append(edu_text.strip())
            elif edu:
                formatted_edu.append(str(edu))
        return '; '.join(formatted_edu)
    
    return str(value)

@register.filter
def format_work_experience(value):
    """Format work experience JSON for display"""
    if not value:
        return ''
    
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    if isinstance(value, list):
        formatted_exp = []
        for exp in value:
            if isinstance(exp, dict):
                job_title = exp.get('job_title', '')
                company = exp.get('company_name', '')
                start_date = exp.get('start_date', '')
                end_date = exp.get('end_date', '')
                
                exp_text = f"{job_title} at {company}"
                if start_date or end_date:
                    exp_text += f" ({start_date} - {end_date})"
                
                formatted_exp.append(exp_text)
            elif exp:
                formatted_exp.append(str(exp))
        return '; '.join(formatted_exp)
    
    return str(value)

@register.filter
def format_projects(value):
    """Format projects JSON for display"""
    if not value:
        return ''
    
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    if isinstance(value, list):
        formatted_projects = []
        for project in value:
            if isinstance(project, dict):
                title = project.get('title', '')
                description = project.get('description', '')
                
                if title:
                    project_text = title
                    if description:
                        project_text += f": {description[:100]}..."
                    formatted_projects.append(project_text)
            elif project:
                formatted_projects.append(str(project))
        return '; '.join(formatted_projects)
    
    return str(value)

@register.filter
def split(value, delimiter):
    """Split a string by delimiter"""
    if not value:
        return []
    return str(value).split(delimiter)

@register.filter
def trim(value):
    """Trim whitespace from string"""
    if not value:
        return ''
    return str(value).strip()
