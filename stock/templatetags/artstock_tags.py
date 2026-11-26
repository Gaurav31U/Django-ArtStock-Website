from django import template

register = template.Library()


@register.filter
def stars(rating):
    """5-item list of 'solid' / 'half' / 'regular' Font Awesome styles for a 0-5 rating."""
    try:
        value = float(rating or 0)
    except (TypeError, ValueError):
        value = 0
    out = []
    for i in range(1, 6):
        if value >= i - 0.25:
            out.append('fa-solid fa-star')
        elif value >= i - 0.75:
            out.append('fa-solid fa-star-half-stroke')
        else:
            out.append('fa-regular fa-star')
    return out

