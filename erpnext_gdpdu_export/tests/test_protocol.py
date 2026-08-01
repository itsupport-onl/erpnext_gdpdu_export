"""Prüfprotokoll aggregation and rendering. Runs without a Frappe site."""

import datetime
import unittest
from decimal import Decimal

from erpnext_gdpdu_export.gdpdu.protocol import Protocol, format_amount_de, format_date_de


class TestFormatting(unittest.TestCase):
	def test_amounts_use_german_notation(self):
		self.assertEqual(format_amount_de(1234567.891), "1.234.567,89")
		self.assertEqual(format_amount_de(-42.5), "-42,50")
		self.assertEqual(format_amount_de(0), "0,00")

	def test_dates_use_german_notation(self):
		self.assertEqual(format_date_de(datetime.date(2024, 1, 31)), "31.01.2024")
		self.assertEqual(format_date_de(""), "")


class TestProtocol(unittest.TestCase):
	def setUp(self):
		self.protocol = Protocol(
			company="Muster GmbH",
			from_date=datetime.date(2024, 1, 1),
			to_date=datetime.date(2024, 12, 31),
			currency="EUR",
			app_version="0.1.0",
			created_by="buchhaltung@example.de",
			created_at=datetime.datetime(2024, 5, 1, 8, 0, 0),
		)

	def test_balanced_journal(self):
		self.protocol.add_amounts(1190, 0)
		self.protocol.add_amounts(0, 1000)
		self.protocol.add_amounts(0, 190)
		self.assertEqual(self.protocol.total_debit, Decimal("1190"))
		self.assertEqual(self.protocol.difference, Decimal("0.00"))
		self.assertTrue(self.protocol.is_balanced)

	def test_unbalanced_journal_is_detected(self):
		self.protocol.add_amounts(100, 0)
		self.protocol.add_amounts(0, 99.99)
		self.assertFalse(self.protocol.is_balanced)
		self.assertEqual(self.protocol.difference, Decimal("0.01"))

	def test_float_cents_do_not_drift(self):
		for _ in range(3):
			self.protocol.add_amounts(0.1, 0.1)
		self.assertTrue(self.protocol.is_balanced)

	def test_repeated_warnings_are_counted(self):
		for name in ("Konto A", "Konto B", "Konto C"):
			self.protocol.add_warning(
				code="missing_account_number",
				message="Für mindestens ein Sachkonto ist keine Kontonummer hinterlegt.",
				hint="Kontonummer nachtragen.",
				sample=name,
			)
		self.assertEqual(len(self.protocol.warnings), 1)
		self.assertEqual(self.protocol.warnings[0].count, 3)
		self.assertEqual(self.protocol.warnings[0].samples, ["Konto A", "Konto B", "Konto C"])

	def test_row_counts(self):
		self.protocol.add_table("journal.csv", "Buchungsjournal", 3)
		self.protocol.add_table("kontenplan.csv", "Kontenplan", 50)
		self.assertEqual(self.protocol.journal_rows, 3)
		self.assertEqual(self.protocol.total_rows, 53)

	def test_text_protocol_contains_the_essentials(self):
		self.protocol.add_table("journal.csv", "Buchungsjournal", 2)
		self.protocol.add_amounts(1000, 1000)
		text = self.protocol.as_text()
		self.assertIn("Muster GmbH", text)
		self.assertIn("01.01.2024 bis 31.12.2024", text)
		self.assertIn("journal.csv", text)
		self.assertIn("1.000,00 EUR", text)
		self.assertIn("Keine Auffälligkeiten.", text)

	def test_text_protocol_counts_records_in_german(self):
		self.protocol.add_table("journal.csv", "Buchungsjournal", 1)
		self.protocol.add_table("kontenplan.csv", "Kontenplan", 1234)
		text = self.protocol.as_text()
		self.assertIn("1 Datensatz", text)
		self.assertIn("1.234 Datensätze", text)

	def test_html_protocol_escapes_data(self):
		self.protocol.company = 'Meier & Sohn <script>alert("x")</script>'
		self.protocol.add_table("journal.csv", "Buchungsjournal", 1)
		html = self.protocol.as_html()
		self.assertNotIn("<script>", html)
		self.assertIn("&amp;", html)

	def test_html_protocol_shows_warnings(self):
		self.protocol.add_warning(code="x", message="Ein Hinweis", hint="Etwas tun")
		html = self.protocol.as_html()
		self.assertIn("Ein Hinweis", html)
		self.assertIn("Etwas tun", html)

	def test_validation_label_reports_missing_check(self):
		self.protocol.validation_message = "Die Datei fehlt."
		self.assertIn("nicht gegen die DTD geprüft", self.protocol.as_html())
