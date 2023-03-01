import datetime as dt
import string

def get_int_from_text(text):
    stripped = "".join(filter(lambda c: c in "1234567890", text))
    if not stripped:
        return 0
    return int(stripped)

def remove_multiple_space(text):
    if not text:
        return text
    while "  " in text:
        text = text.replace("  ", " ")
    return text

def parse_german_date(dateText):
	try:
		return dt.datetime.strptime(dateText,"%d.%m.%Y")
	except ValueError:
		return dateText

def remove_non_printable(text):
    return "".join(list(filter(lambda x: x in string.printable, text)))