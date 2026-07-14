"""Small formatting helpers shared across app pages."""


def parse_money(s):
    """Converts a Sheets-formatted currency string ("$4,175.82", "-", "") to a float."""
    if s is None:
        return 0.0
    s = str(s).strip()
    if s in ("", "-", "—"):
        return 0.0
    s = s.replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    try:
        return float(s)
    except ValueError:
        return 0.0


def fmt_money(x):
    return f"${x:,.2f}"
