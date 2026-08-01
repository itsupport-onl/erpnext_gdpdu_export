"""CSV format tests (VariableLength). Runs without a Frappe site."""

import datetime
import unittest

from erpnext_gdpdu_export.gdpdu import schema
from erpnext_gdpdu_export.gdpdu.csv_writer import format_row, render_csv, write_csv_file

JOURNAL_ROW = {
	"JournalID": "GLE-0001",
	"Buchungsdatum": datetime.date(2024, 3, 1),
	"Belegdatum": datetime.date(2024, 3, 1),
	"Belegart": "Sales Invoice",
	"Belegnummer": "ACC-SINV-2024-00001",
	"Konto": "4400",
	"Kontobezeichnung": "Erlöse 19 % USt",
	"Soll": 0,
	"Haben": 1000.0,
	"Waehrung": "EUR",
	"GegenparteiTyp": "Customer",
	"Gegenpartei": "Muster GmbH",
	"Gegenkonto": "1400",
	"Buchungstext": "Rechnung\r\nMärz",
	"Kostenstelle": "Hauptkostenstelle - M",
	"ErfasstAm": datetime.datetime(2024, 3, 1, 9, 30, 15),
	"ErfasstUm": datetime.datetime(2024, 3, 1, 9, 30, 15),
	"ErfasstVon": "buchhaltung@example.de",
}


class TestFormatRow(unittest.TestCase):
	def test_column_order_matches_header(self):
		row = format_row(schema.JOURNAL, JOURNAL_ROW)
		self.assertEqual(len(row), len(schema.JOURNAL.header))
		self.assertEqual(row[0], "GLE-0001")
		self.assertEqual(row[1], "20240301")

	def test_amounts_dates_and_time(self):
		values = dict(zip(schema.JOURNAL.header, format_row(schema.JOURNAL, JOURNAL_ROW), strict=True))
		self.assertEqual(values["Soll"], "0,00")
		self.assertEqual(values["Haben"], "1000,00")
		self.assertEqual(values["ErfasstAm"], "20240301")
		self.assertEqual(values["ErfasstUm"], "09:30:15")

	def test_line_breaks_are_removed(self):
		values = dict(zip(schema.JOURNAL.header, format_row(schema.JOURNAL, JOURNAL_ROW), strict=True))
		self.assertEqual(values["Buchungstext"], "Rechnung März")

	def test_missing_keys_become_empty(self):
		row = format_row(schema.CUSTOMERS, {"Kennung": "CUST-0001"})
		self.assertEqual(row, ["CUST-0001", "", "", "", "", "", ""])


class TestRenderCsv(unittest.TestCase):
	def test_header_and_crlf(self):
		content = render_csv(schema.JOURNAL, [JOURNAL_ROW])
		lines = content.split("\r\n")
		self.assertEqual(lines[0], ";".join(schema.JOURNAL.header))
		self.assertEqual(len(lines), 3)  # header, one record, trailing empty
		self.assertEqual(lines[2], "")
		self.assertNotIn("\n\n", content)

	def test_semicolon_in_data_is_encapsulated(self):
		content = render_csv(schema.CUSTOMERS, [{"Kennung": "C1", "Name": "Meier; Sohn"}])
		self.assertIn('"Meier; Sohn"', content)

	def test_quotes_are_doubled(self):
		content = render_csv(schema.CUSTOMERS, [{"Kennung": "C1", "Name": 'Zum "Adler"'}])
		self.assertIn('"Zum ""Adler"""', content)

	def test_plain_values_are_not_encapsulated(self):
		content = render_csv(schema.CUSTOMERS, [{"Kennung": "C1", "Name": "Muster GmbH"}])
		self.assertIn("C1;Muster GmbH;", content)

	def test_empty_table_keeps_header(self):
		content = render_csv(schema.SUPPLIERS, [])
		self.assertEqual(content, ";".join(schema.SUPPLIERS.header) + "\r\n")


class TestWriteCsvFile(unittest.TestCase):
	def test_utf8_without_bom_and_crlf(self):
		import tempfile
		from pathlib import Path

		with tempfile.TemporaryDirectory() as folder:
			path = Path(folder) / "debitoren.csv"
			count = write_csv_file(schema.CUSTOMERS, [{"Kennung": "C1", "Name": "Müller KG"}], path)
			raw = path.read_bytes()

		self.assertEqual(count, 1)
		self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))
		self.assertIn("Müller KG".encode(), raw)
		self.assertTrue(raw.endswith(b"\r\n"))
		self.assertNotIn(b"\n\n", raw)
