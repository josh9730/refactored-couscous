import datetime
import validators


# Custom Cerberus validators
def is_func(field, value, error):
    """Check if string from YAML matches a valid command"""

    j2_func = [
        "rh",
        "cmd-rh",
        "noc",
        "cmd-noc",
        "expand-noc",
        "core",
        "cmd-core",
        "expand-core",
        "note",
        "jumper",
    ]
    if value not in j2_func:
        error(field, f"Must be one of {j2_func}")


def is_24h(field, value, error):
    """Times me in 24h format"""

    if len(str(value)) < 4:
        error(field, "Must be in 24h format")


def is_date(field, value, error):
    """Check if datetime object or 'today'"""

    if value != "today":
        if type(value) != datetime.date:
            error(field, 'Must be in YYYY-MM-DD format or "today"')


def is_url(field, value, error):
    """Check if string is a valid URL"""

    try:
        if not validators.url(value):
            error(field, "Must be a valid url")
    except TypeError:
        pass
