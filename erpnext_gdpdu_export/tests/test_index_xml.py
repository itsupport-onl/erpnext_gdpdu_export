"""index.xml generation and DTD validation. Runs without a Frappe site.

The DTD is a third-party artefact and not part of this repository. The validation
test is skipped unless the file is available in ``resources/`` or via the
environment variable ``GDPDU_DTD_PATH``.
"""

import datetime
import os
import unittest
from pathlib import Path
from xml.etree import ElementTree

from erpnext_gdpdu_export.gdpdu import schema
from erpnext_gdpdu_export.gdpdu.dtd import get_bundled_dtd, validate_index_xml
from erpnext_gdpdu_export.gdpdu.index_xml import build_index_xml, escape

FROM_DATE = datetime.date(2024, 1, 1)
TO_DATE = datetime.date(2024, 12, 31)


def build_sample() -> str:
	return build_index_xml(
		schema.get_tables(),
		supplier_name="Muster GmbH & Co. KG",
		supplier_location="Berlin",
		comment="GoBD-Datentraegerueberlassung 20240101-20241231",
		from_date=FROM_DATE,
		to_date=TO_DATE,
	)


def load_dtd() -> bytes | None:
	path = os.environ.get("GDPDU_DTD_PATH")
	if path and Path(path).is_file():
		return Path(path).read_bytes()
	return get_bundled_dtd()


class TestEscape(unittest.TestCase):
	def test_forbidden_characters(self):
		self.assertEqual(escape('a & b < c > d "e"'), "a &amp; b &lt; c &gt; d &quot;e&quot;")


class TestBuildIndexXml(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.xml = build_sample()
		cls.root = ElementTree.fromstring(cls.xml)

	def test_declaration_and_doctype(self):
		self.assertTrue(self.xml.startswith('<?xml version="1.0" encoding="UTF-8"?>\n'))
		self.assertIn('<!DOCTYPE DataSet SYSTEM "gdpdu-01-08-2002.dtd">', self.xml)

	def test_data_supplier_is_complete(self):
		supplier = self.root.find("DataSupplier")
		self.assertEqual([child.tag for child in supplier], ["Name", "Location", "Comment"])
		self.assertEqual(supplier.findtext("Name"), "Muster GmbH & Co. KG")

	def test_one_table_per_schema(self):
		tables = self.root.findall("Media/Table")
		self.assertEqual(len(tables), len(schema.get_tables()))
		self.assertEqual(
			[table.findtext("URL") for table in tables],
			[table.filename for table in schema.get_tables()],
		)

	def test_table_child_order_follows_dtd(self):
		table = self.root.find("Media/Table")
		self.assertEqual(
			[child.tag for child in table],
			[
				"URL",
				"Name",
				"Description",
				"Validity",
				"UTF8",
				"DecimalSymbol",
				"DigitGroupingSymbol",
				"Range",
				"VariableLength",
			],
		)

	def test_header_line_is_skipped(self):
		table = self.root.find("Media/Table")
		self.assertEqual(table.find("Range").findtext("From"), "2")

	def test_validity_carries_the_export_period(self):
		validity = self.root.find("Media/Table/Validity")
		self.assertEqual(validity.find("Range").findtext("From"), "20240101")
		self.assertEqual(validity.find("Range").findtext("To"), "20241231")
		self.assertEqual(validity.findtext("Format"), "YYYYMMDD")

	def test_format_declarations(self):
		table = self.root.find("Media/Table")
		self.assertEqual(table.findtext("DecimalSymbol"), ",")
		self.assertEqual(table.findtext("DigitGroupingSymbol"), ".")
		variable_length = table.find("VariableLength")
		self.assertEqual(variable_length.findtext("ColumnDelimiter"), ";")
		self.assertEqual(variable_length.findtext("TextEncapsulator"), '"')

	def test_record_delimiter_survives_xml_normalisation(self):
		# A literal CR would be normalised to LF by any XML parser.
		self.assertIn("<RecordDelimiter>&#13;&#10;</RecordDelimiter>", self.xml)
		self.assertEqual(self.root.find("Media/Table/VariableLength").findtext("RecordDelimiter"), "\r\n")

	def test_key_columns_come_first_and_in_file_order(self):
		variable_length = self.root.find("Media/Table/VariableLength")
		declared = [
			child.findtext("Name")
			for child in variable_length
			if child.tag in ("VariablePrimaryKey", "VariableColumn")
		]
		self.assertEqual(tuple(declared), schema.JOURNAL.header)
		self.assertEqual(variable_length.find("VariablePrimaryKey").findtext("Name"), "JournalID")

	def test_column_types(self):
		columns = {
			child.findtext("Name"): child
			for child in self.root.find("Media/Table/VariableLength")
			if child.tag in ("VariablePrimaryKey", "VariableColumn")
		}
		self.assertEqual(columns["Soll"].find("Numeric").findtext("Accuracy"), "2")
		self.assertEqual(columns["Buchungsdatum"].find("Date").findtext("Format"), "YYYYMMDD")
		self.assertIsNotNone(columns["Belegart"].find("AlphaNumeric"))
		self.assertEqual(columns["Waehrung"].findtext("MaxLength"), "3")

	def test_maps_explain_encoded_values(self):
		accounts = [
			table for table in self.root.findall("Media/Table") if table.findtext("URL") == "kontenplan.csv"
		][0]
		maps = {
			child.findtext("Name"): child.findall("Map")
			for child in accounts.find("VariableLength")
			if child.tag in ("VariablePrimaryKey", "VariableColumn")
		}
		self.assertEqual(
			[(item.findtext("From"), item.findtext("To")) for item in maps["IstGruppe"]],
			[("0", "Nein"), ("1", "Ja")],
		)

	def test_foreign_key_points_to_an_existing_table(self):
		journal = self.root.find("Media/Table")
		foreign_key = journal.find("VariableLength/ForeignKey")
		self.assertEqual(foreign_key.findtext("Name"), "Konto")
		self.assertEqual(foreign_key.findtext("References"), "Kontenplan")
		table_names = {table.findtext("Name") for table in self.root.findall("Media/Table")}
		self.assertIn(foreign_key.findtext("References"), table_names)

	def test_empty_table_list_is_rejected(self):
		with self.assertRaises(ValueError):
			build_index_xml(
				(),
				supplier_name="x",
				supplier_location="y",
				comment="z",
				from_date=FROM_DATE,
				to_date=TO_DATE,
			)


class TestDtdValidation(unittest.TestCase):
	def test_index_xml_is_dtd_valid(self):
		dtd = load_dtd()
		if not dtd:
			self.skipTest("gdpdu-01-08-2002.dtd not available (see resources/README.md)")

		result = validate_index_xml(build_sample(), dtd)
		if not result.performed:
			self.skipTest(result.skipped_reason)
		self.assertTrue(result.valid, "\n".join(result.errors))

	def test_broken_xml_is_reported(self):
		dtd = load_dtd()
		if not dtd:
			self.skipTest("gdpdu-01-08-2002.dtd not available (see resources/README.md)")

		broken = build_sample().replace("<Version>1.0</Version>", "")
		result = validate_index_xml(broken, dtd)
		if not result.performed:
			self.skipTest(result.skipped_reason)
		self.assertFalse(result.valid)
		self.assertTrue(result.errors)

	def test_missing_dtd_is_not_an_error(self):
		result = validate_index_xml(build_sample(), None)
		self.assertFalse(result.performed)
		self.assertTrue(result.skipped_reason)
