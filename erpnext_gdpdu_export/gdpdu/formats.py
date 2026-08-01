"""Value formatting for the GDPdU description standard.

All format decisions are fixed by KONZEPT.md section 2 and must not be changed
without an explicit decision. This module has no Frappe dependency so it can be
unit tested with a plain Python interpreter.
"""

from __future__ import annotations

import datetime
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Declared in index.xml for every Date column.
DATE_FORMAT = "YYYYMMDD"
# Declared as a Map on time columns (standard 1.6 has no native time type).
TIME_FORMAT = "HH:MM:SS"

DECIMAL_SYMBOL = ","
DIGIT_GROUPING_SYMBOL = "."

# Control characters would break the record structure of a CSV file.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]+")
_MULTI_SPACE = re.compile(r" {2,}")


def format_date(value) -> str:
	"""Return a date as ``YYYYMMDD``. Empty values stay empty."""
	if value is None or value == "":
		return ""

	if isinstance(value, datetime.datetime):
		value = value.date()
	if isinstance(value, datetime.date):
		return value.strftime("%Y%m%d")

	text = str(value).strip()
	if not text:
		return ""
	if len(text) == 8 and text.isdigit():
		return text
	try:
		return datetime.datetime.strptime(text[:10], "%Y-%m-%d").strftime("%Y%m%d")
	except ValueError as exc:
		raise ValueError(f"Cannot format {value!r} as a GDPdU date") from exc


def format_time(value) -> str:
	"""Return the time part of a value as ``HH:MM:SS``. Empty values stay empty."""
	if value is None or value == "":
		return ""

	if isinstance(value, datetime.datetime):
		value = value.time()
	if isinstance(value, datetime.time):
		return value.strftime("%H:%M:%S")
	if isinstance(value, datetime.timedelta):
		total = int(value.total_seconds()) % 86400
		return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"

	text = str(value).strip()
	if not text:
		return ""
	# "2024-01-31 10:12:13.123456" or "10:12:13"
	if " " in text:
		text = text.split(" ", 1)[1]
	text = text.split(".", 1)[0]
	try:
		return datetime.datetime.strptime(text, "%H:%M:%S").strftime("%H:%M:%S")
	except ValueError as exc:
		raise ValueError(f"Cannot format {value!r} as a GDPdU time") from exc


def format_numeric(value, accuracy: int = 2) -> str:
	"""Return an amount with ``accuracy`` decimals, comma as decimal symbol.

	No digit grouping, negative numbers carry a leading ``-`` without a space.
	Empty values stay empty so that "no value" and "zero" remain distinguishable.
	"""
	if value is None or value == "":
		return ""

	try:
		# repr() keeps the decimal literal a user would expect from a float.
		number = Decimal(repr(value) if isinstance(value, float) else str(value).strip())
	except InvalidOperation as exc:
		raise ValueError(f"Cannot format {value!r} as a GDPdU number") from exc

	quantized = number.quantize(Decimal(1).scaleb(-accuracy), rounding=ROUND_HALF_UP)
	if quantized == 0:
		# Avoid "-0,00" for tiny negative rounding remainders.
		quantized = abs(quantized)
	return f"{quantized:f}".replace(".", DECIMAL_SYMBOL)


def clean_text(value) -> str:
	"""Return a single-line text without control characters."""
	if value is None:
		return ""
	if isinstance(value, bool):
		return "1" if value else "0"
	if isinstance(value, datetime.date | datetime.datetime):
		return str(value)

	text = _CONTROL_CHARS.sub(" ", str(value))
	return _MULTI_SPACE.sub(" ", text).strip()
