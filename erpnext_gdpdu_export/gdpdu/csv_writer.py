"""Writes VariableLength CSV files exactly as declared in index.xml.

Format (KONZEPT.md section 2): UTF-8 without BOM, ``;`` as column delimiter,
CRLF as record delimiter, ``"`` as text encapsulator with doubling, one header
line that index.xml skips via ``<Range><From>2</From></Range>``.

No Frappe dependency, so this module is unit testable with a plain interpreter.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import TextIO

from .formats import clean_text, format_date, format_numeric, format_time
from .schema import ALPHANUMERIC, DATE, NUMERIC, Column, Table

ENCODING = "utf-8"
COLUMN_DELIMITER = ";"
RECORD_DELIMITER = "\r\n"
TEXT_ENCAPSULATOR = '"'

#: Columns declared as AlphaNumeric that carry a time of day (see schema maps).
TIME_COLUMNS = frozenset({"ErfasstUm"})


def format_value(column: Column, value) -> str:
	"""Return the CSV representation of ``value`` for ``column``."""
	if column.type == NUMERIC:
		return format_numeric(value, accuracy=column.accuracy or 0)
	if column.type == DATE:
		return format_date(value)
	if column.type == ALPHANUMERIC and column.name in TIME_COLUMNS:
		return format_time(value)
	return clean_text(value)


def format_row(table: Table, row: dict) -> list[str]:
	"""Return one CSV record as a list of already formatted strings."""
	return [format_value(column, row.get(column.name)) for column in table.columns]


def open_writer(stream: TextIO):
	return csv.writer(
		stream,
		delimiter=COLUMN_DELIMITER,
		quotechar=TEXT_ENCAPSULATOR,
		doublequote=True,
		quoting=csv.QUOTE_MINIMAL,
		lineterminator=RECORD_DELIMITER,
	)


def write_csv(table: Table, rows: Iterable[dict], stream: TextIO) -> int:
	"""Write header and records of ``table`` to ``stream``; return the record count.

	``stream`` must be opened with ``newline=""`` and encoding UTF-8 so the record
	delimiter stays CRLF on every platform.
	"""
	writer = open_writer(stream)
	writer.writerow(table.header)

	count = 0
	for row in rows:
		writer.writerow(format_row(table, row))
		count += 1
	return count


def write_csv_file(table: Table, rows: Iterable[dict], path) -> int:
	"""Write ``rows`` into the file ``path`` (UTF-8, no BOM); return the record count."""
	with open(path, "w", encoding=ENCODING, newline="") as handle:
		return write_csv(table, rows, handle)


def render_csv(table: Table, rows: Iterable[dict]) -> str:
	"""Return the complete CSV content as a string (used by tests and previews)."""
	buffer = io.StringIO(newline="")
	write_csv(table, rows, buffer)
	return buffer.getvalue()
