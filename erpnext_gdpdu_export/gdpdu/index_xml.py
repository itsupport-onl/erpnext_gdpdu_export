"""Generates index.xml from the schema definitions in :mod:`gdpdu.schema`.

Element names and their order follow the DTD ``gdpdu-01-08-2002.dtd``:

    Table            (URL, Name?, Description?, Validity?, UTF8?, (DecimalSymbol,
                      DigitGroupingSymbol)?, SkipNumBytes?, Range?, Epoch?,
                      (VariableLength | FixedLength))
    VariableLength   (ColumnDelimiter?, RecordDelimiter?, TextEncapsulator?,
                      ((VariablePrimaryKey+, VariableColumn*) | (VariableColumn+)),
                      ForeignKey*)
    VariableColumn   (Name, Description?, (Numeric | (AlphaNumeric, MaxLength?) | Date), Map*)

The XML is serialised by hand instead of via ElementTree so that the record
delimiter can be written as the character references ``&#13;&#10;`` — an XML
parser would otherwise normalise a literal CR away.

No Frappe dependency, so this module is unit testable with a plain interpreter.
"""

from __future__ import annotations

from .csv_writer import COLUMN_DELIMITER, TEXT_ENCAPSULATOR
from .formats import DECIMAL_SYMBOL, DIGIT_GROUPING_SYMBOL, format_date
from .schema import ALPHANUMERIC, DATE, NUMERIC, Column, Table

DTD_FILE_NAME = "gdpdu-01-08-2002.dtd"
INDEX_FILE_NAME = "index.xml"

#: Version of the data delivery, not of the description standard.
DATA_SET_VERSION = "1.0"

#: The header line of every CSV file is skipped by starting at record 2.
FIRST_DATA_RECORD = 2

INDENT = "\t"


def escape(text) -> str:
	"""Escape the characters the DTD forbids in element content."""
	if text is None:
		return ""
	return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


class _Builder:
	"""Minimal, order-preserving XML serialiser."""

	def __init__(self):
		self.lines: list[str] = []
		self.level = 0

	def open(self, tag: str) -> None:
		self.lines.append(f"{INDENT * self.level}<{tag}>")
		self.level += 1

	def close(self, tag: str) -> None:
		self.level -= 1
		self.lines.append(f"{INDENT * self.level}</{tag}>")

	def empty(self, tag: str) -> None:
		self.lines.append(f"{INDENT * self.level}<{tag}/>")

	def leaf(self, tag: str, value, *, raw: bool = False) -> None:
		content = str(value) if raw else escape(value)
		self.lines.append(f"{INDENT * self.level}<{tag}>{content}</{tag}>")

	def render(self) -> str:
		return "\n".join(self.lines)


def _write_column(builder: _Builder, column: Column, tag: str) -> None:
	builder.open(tag)
	builder.leaf("Name", column.name)
	if column.description:
		builder.leaf("Description", column.description)

	if column.type == NUMERIC:
		if column.accuracy is None:
			builder.empty("Numeric")
		else:
			builder.open("Numeric")
			builder.leaf("Accuracy", column.accuracy)
			builder.close("Numeric")
	elif column.type == DATE:
		builder.open("Date")
		builder.leaf("Format", column.date_format)
		builder.close("Date")
	elif column.type == ALPHANUMERIC:
		builder.empty("AlphaNumeric")
		if column.max_length is not None:
			builder.leaf("MaxLength", column.max_length)

	for value_map in column.maps:
		builder.open("Map")
		if value_map.description:
			builder.leaf("Description", value_map.description)
		builder.leaf("From", value_map.from_value)
		builder.leaf("To", value_map.to_value)
		builder.close("Map")

	builder.close(tag)


def _write_table(builder: _Builder, table: Table, from_date, to_date) -> None:
	builder.open("Table")
	builder.leaf("URL", table.filename)
	builder.leaf("Name", table.name)
	builder.leaf("Description", table.description)

	builder.open("Validity")
	builder.open("Range")
	builder.leaf("From", format_date(from_date))
	builder.leaf("To", format_date(to_date))
	builder.close("Range")
	builder.leaf("Format", "YYYYMMDD")
	builder.close("Validity")

	builder.empty("UTF8")
	builder.leaf("DecimalSymbol", DECIMAL_SYMBOL)
	builder.leaf("DigitGroupingSymbol", DIGIT_GROUPING_SYMBOL)

	# Skip the human readable header line.
	builder.open("Range")
	builder.leaf("From", FIRST_DATA_RECORD)
	builder.close("Range")

	builder.open("VariableLength")
	builder.leaf("ColumnDelimiter", COLUMN_DELIMITER)
	builder.leaf("RecordDelimiter", "&#13;&#10;", raw=True)
	builder.leaf("TextEncapsulator", TEXT_ENCAPSULATOR)

	for column in table.key_columns:
		_write_column(builder, column, "VariablePrimaryKey")
	for column in table.data_columns:
		_write_column(builder, column, "VariableColumn")

	for foreign_key in table.foreign_keys:
		builder.open("ForeignKey")
		for column_name in foreign_key.columns:
			builder.leaf("Name", column_name)
		builder.leaf("References", foreign_key.references)
		builder.close("ForeignKey")

	builder.close("VariableLength")
	builder.close("Table")


def build_index_xml(
	tables: tuple[Table, ...],
	*,
	supplier_name: str,
	supplier_location: str,
	comment: str,
	from_date,
	to_date,
	media_name: str = "Export",
) -> str:
	"""Return the complete index.xml for ``tables`` as a string."""
	if not tables:
		raise ValueError("index.xml needs at least one table")

	builder = _Builder()
	builder.lines.append('<?xml version="1.0" encoding="UTF-8"?>')
	builder.lines.append(f'<!DOCTYPE DataSet SYSTEM "{DTD_FILE_NAME}">')

	builder.open("DataSet")
	builder.leaf("Version", DATA_SET_VERSION)

	builder.open("DataSupplier")
	builder.leaf("Name", supplier_name)
	builder.leaf("Location", supplier_location)
	builder.leaf("Comment", comment)
	builder.close("DataSupplier")

	builder.open("Media")
	builder.leaf("Name", media_name)
	for table in tables:
		_write_table(builder, table, from_date, to_date)
	builder.close("Media")

	builder.close("DataSet")
	return builder.render() + "\n"
