from django import template

register = template.Library()

@register.filter
def doctor_display(value):
    """Show one consistent doctor honorific without changing stored data."""
    name = str(value or '').strip()
    if not name:
        return 'Dr.'
    return name if name.lower().startswith('dr.') else f'Dr. {name}'

@register.filter
def get_doctor_image(doctor_id):
    """
    Returns a consistent distinct profile image URL for a given doctor ID.
    This avoids all doctors sharing the same generic image, while requiring no DB schema changes.
    """
    try:
        did = int(doctor_id)
    except (ValueError, TypeError):
        did = 0

    urls = [
        "https://images.unsplash.com/photo-1612349317150-e413f6a5b16d",
        "https://images.unsplash.com/photo-1559839734-2b71ea197ec2",
        "https://images.unsplash.com/photo-1594824432257-f679df3f7a6f",
        "https://images.unsplash.com/photo-1622253692010-333f2da6031d",
        "https://images.unsplash.com/photo-1537368910025-700350fe46c7",
        "https://images.unsplash.com/photo-1527613426406-8b368db51fba",
        "https://images.unsplash.com/photo-1651008376811-b932efdc22eb",
        "https://images.unsplash.com/photo-1579684385127-1ef15d508118",
        "https://images.unsplash.com/photo-1618398463953-e5757967928f",
        "https://images.unsplash.com/photo-1614608682850-e0d6ed316d47"
    ]
    return urls[did % len(urls)]
