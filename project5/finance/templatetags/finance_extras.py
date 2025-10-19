from django import template

register = template.Library()


@register.filter
def split_tags(value):
    if not value:
        return []
    return [tag.strip() for tag in value.split(",") if tag.strip()]
