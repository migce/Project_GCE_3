from django import template

register = template.Library()


@register.filter(name='nsp')
def number_with_space(value, digits=0):
    """Format number with spaces as thousands separator.

    Usage: {{ value|nsp }} or {{ value|nsp:1 }}
    - digits: decimal places to keep (int)
    - preserves sign; returns original value if not a number
    """
    try:
        d = int(digits or 0)
    except Exception:
        d = 0

    # Short-circuit None/empty
    if value is None or value == '':
        if d <= 0:
            return '0'
        return f"{0:.{d}f}"

    # Convert to float if possible
    try:
        x = float(value)
    except Exception:
        # Already a string or non-numeric; return as-is
        return value

    if d <= 0:
        s = f"{int(round(x)):,}"
    else:
        s = f"{x:,.{d}f}"

    # Replace comma with space; keep dot as decimal separator
    return s.replace(',', ' ')

