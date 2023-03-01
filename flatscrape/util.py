import datetime as dt
import logging
import string

logger = logging.getLogger(__name__)

def get_int_from_text(text):
    """Can be used when some number must be generated from a text with numbers.
    This may not make sense, for example 10.01 -> 1001."""
    stripped = "".join(filter(lambda c: c in "1234567890", text))
    if not stripped:
        return 0
    return int(stripped)

def remove_multiple_space(text):
    """Replace all occurrences of at least two spaces with a single space."""
    if not text:
        return text
    while "  " in text:
        text = text.replace("  ", " ")
    return text

def parse_german_date(dateText):
    """Generate a datetime object from a german text string (dd.mm.yyyy)"""
    try:
        return dt.datetime.strptime(dateText,"%d.%m.%Y")
    except ValueError:
        return dateText

def remove_non_printable(text):
    """Remove all non printable characters from a string."""
    return "".join(list(filter(lambda x: x in string.printable, text)))