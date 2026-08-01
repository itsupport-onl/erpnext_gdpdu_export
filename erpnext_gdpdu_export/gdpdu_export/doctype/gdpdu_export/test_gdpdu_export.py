"""Integration tests: a complete export package built on Frappe fixtures.

Needs a site: ``bench --site <site> run-tests --app erpnext_gdpdu_export``.
"""

from __future__ import annotations

import csv
import io
import zipfile
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import nowdate

from erpnext_gdpdu_export.gdpdu.dtd import get_dtd, validate_index_xml
from erpnext_gdpdu_export.gdpdu.extractors import ExtractionContext, journal
from erpnext_gdpdu_export.gdpdu.index_xml import INDEX_FILE_NAME
from erpnext_gdpdu_export.gdpdu.package import PROTOCOL_FILE_NAME, README_FILE_NAME, build_package
from erpnext_gdpdu_export.gdpdu.protocol import Protocol
from erpnext_gdpdu_export.gdpdu.schema import get_tables

COMPANY = "_Test GDPdU GmbH"
ABBR = "TGDP"
CUSTOMER = "_Test GDPdU Kundin"
SUPPLIER = "_Test GDPdU Lieferant"

ACCOUNTS = (
	("1200", "Bank GDPdU", "Asset", "Bank"),
	("1400", "Forderungen GDPdU", "Asset", "Receivable"),
	("1600", "Verbindlichkeiten GDPdU", "Liability", "Payable"),
	("1776", "Umsatzsteuer GDPdU", "Liability", "Tax"),
	("4980", "Bürobedarf GDPdU", "Expense", ""),
	("8400", "Erlöse GDPdU", "Income", ""),
)


class TestGDPdUExport(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.year = int(nowdate()[:4])
		cls.from_date = f"{cls.year}-01-01"
		cls.to_date = f"{cls.year}-12-31"
		create_fixtures()
		frappe.db.commit()

	def build(self):
		return build_package(COMPANY, self.from_date, self.to_date)

	def read_package(self, result) -> dict[str, bytes]:
		with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
			return {name: archive.read(name) for name in archive.namelist()}

	def read_csv(self, files: dict[str, bytes], filename: str) -> list[dict]:
		content = files[filename].decode("utf-8")
		self.assertIn("\r\n", content)
		reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=";", quotechar='"')
		return list(reader)

	# ------------------------------------------------------------- package

	def test_package_contains_every_declared_file(self):
		files = self.read_package(self.build())

		self.assertIn(INDEX_FILE_NAME, files)
		self.assertIn(PROTOCOL_FILE_NAME, files)
		self.assertIn(README_FILE_NAME, files)
		for table in get_tables():
			self.assertIn(table.filename, files)

	def test_index_xml_declares_every_file_in_the_package(self):
		files = self.read_package(self.build())
		index = files[INDEX_FILE_NAME].decode("utf-8")

		for table in get_tables():
			self.assertIn(f"<URL>{table.filename}</URL>", index)

	def test_index_xml_is_valid_against_the_dtd(self):
		dtd = get_dtd()
		if not dtd.content:
			self.skipTest("gdpdu-01-08-2002.dtd is not configured on this site")

		files = self.read_package(self.build())
		result = validate_index_xml(files[INDEX_FILE_NAME].decode("utf-8"), dtd.content)
		if not result.performed:
			self.skipTest(result.skipped_reason)
		self.assertTrue(result.valid, "\n".join(result.errors))

	# -------------------------------------------------------------- content

	def test_journal_contains_the_test_bookings(self):
		files = self.read_package(self.build())
		rows = self.read_csv(files, "journal.csv")

		accounts = {row["Konto"] for row in rows}
		self.assertIn("1400", accounts)
		self.assertIn("8400", accounts)
		self.assertIn("1776", accounts)

		revenue = [row for row in rows if row["Konto"] == "8400"][0]
		self.assertEqual(revenue["Haben"], "1000,00")
		self.assertEqual(revenue["Soll"], "0,00")
		self.assertEqual(revenue["Waehrung"], "EUR")
		self.assertEqual(len(revenue["Buchungsdatum"]), 8)
		self.assertRegex(revenue["ErfasstUm"], r"^\d{2}:\d{2}:\d{2}$")

		receivable = [row for row in rows if row["Konto"] == "1400"][0]
		self.assertEqual(receivable["GegenparteiTyp"], "Customer")
		self.assertEqual(receivable["Gegenpartei"], CUSTOMER)

	def test_debit_equals_credit(self):
		result = self.build()
		self.assertTrue(result.protocol.is_balanced, result.protocol.as_text())
		self.assertGreater(result.protocol.journal_rows, 0)

	def test_chunked_reading_returns_the_same_journal(self):
		# The journal is paged by (posting_date, creation, name); a small chunk
		# size must not lose, duplicate or reorder rows.
		full = [row["JournalID"] for row in journal.iter_rows(self.context())]
		chunked = [row["JournalID"] for row in journal.iter_rows(self.context(chunk_size=2))]

		self.assertGreater(len(full), 2)
		self.assertEqual(full, chunked)
		self.assertEqual(len(set(chunked)), len(chunked))

	def context(self, **kwargs) -> ExtractionContext:
		return ExtractionContext(
			company=COMPANY,
			from_date=self.from_date,
			to_date=self.to_date,
			currency="EUR",
			protocol=Protocol(),
			**kwargs,
		)

	def test_chart_of_accounts_uses_account_numbers(self):
		files = self.read_package(self.build())
		rows = self.read_csv(files, "kontenplan.csv")

		by_key = {row["Konto"]: row for row in rows}
		self.assertIn("8400", by_key)
		self.assertEqual(by_key["8400"]["Wurzeltyp"], "Income")
		self.assertEqual(by_key["8400"]["IstGruppe"], "0")
		self.assertEqual(by_key["8400"]["Waehrung"], "EUR")

	def test_customers_and_suppliers_with_movements_are_exported(self):
		files = self.read_package(self.build())

		customers = self.read_csv(files, "debitoren.csv")
		self.assertEqual([row["Kennung"] for row in customers], [CUSTOMER])
		self.assertEqual(customers[0]["Ort"], "Berlin")
		self.assertEqual(customers[0]["PLZ"], "10115")
		self.assertEqual(customers[0]["UStIdNr"], "DE123456789")

		suppliers = self.read_csv(files, "kreditoren.csv")
		self.assertEqual([row["Kennung"] for row in suppliers], [SUPPLIER])

	def test_tax_accounts_carry_their_rate(self):
		files = self.read_package(self.build())
		rows = {row["Steuerkonto"]: row for row in self.read_csv(files, "steuerkennzeichen.csv")}

		self.assertIn("1776", rows)
		self.assertEqual(rows["1776"]["Satz"], "19,00")

	def test_period_outside_of_the_bookings_yields_an_empty_journal(self):
		result = build_package(COMPANY, f"{self.year - 5}-01-01", f"{self.year - 5}-12-31")

		self.assertEqual(result.protocol.journal_rows, 0)
		self.assertIn("no_bookings", [warning.code for warning in result.protocol.warnings])

	def test_protocol_lists_every_table(self):
		result = self.build()
		self.assertEqual(
			[table.filename for table in result.protocol.tables],
			[table.filename for table in get_tables()],
		)

	# ------------------------------------------------------------- document

	def test_fiscal_year_fills_the_period(self):
		year = frappe.get_all("Fiscal Year", fields=["name", "year_start_date", "year_end_date"], limit=1)[0]

		doc = frappe.get_doc(
			{
				"doctype": "GDPdU Export",
				"company": COMPANY,
				"period_type": "Geschäftsjahr",
				"fiscal_year": year.name,
			}
		)
		doc.insert()

		self.assertEqual(str(doc.from_date), str(year.year_start_date))
		self.assertEqual(str(doc.to_date), str(year.year_end_date))
		self.assertEqual(doc.status, "Entwurf")

	def test_reversed_period_is_rejected(self):
		doc = frappe.get_doc(
			{
				"doctype": "GDPdU Export",
				"company": COMPANY,
				"period_type": "Benutzerdefiniert",
				"from_date": self.to_date,
				"to_date": self.from_date,
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_start_export_queues_a_background_job(self):
		doc = frappe.get_doc(
			{
				"doctype": "GDPdU Export",
				"company": COMPANY,
				"period_type": "Benutzerdefiniert",
				"from_date": self.from_date,
				"to_date": self.to_date,
			}
		).insert()

		with patch("frappe.enqueue") as enqueue:
			doc.start_export()

		self.assertTrue(enqueue.called)
		self.assertEqual(enqueue.call_args.kwargs["queue"], "long")
		self.assertEqual(enqueue.call_args.kwargs["export_name"], doc.name)
		self.assertEqual(frappe.db.get_value("GDPdU Export", doc.name, "status"), "In Warteschlange")

	def test_export_scope_matches_the_schema(self):
		from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export import (
			get_export_scope,
		)

		self.assertEqual(
			[entry["filename"] for entry in get_export_scope()],
			[table.filename for table in get_tables()],
		)


# ---------------------------------------------------------------- fixtures


def create_fixtures() -> None:
	create_company()
	accounts = {row[0]: create_account(row) for row in ACCOUNTS}
	create_party("Customer", CUSTOMER, "DE123456789")
	create_party("Supplier", SUPPLIER, "DE987654321")
	create_bookings(accounts)


def create_company() -> None:
	if frappe.db.exists("Company", COMPANY):
		return

	frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": COMPANY,
			"abbr": ABBR,
			"default_currency": "EUR",
			"country": "Germany",
		}
	).insert()


def create_account(row) -> str:
	number, name, root_type, account_type = row
	existing = frappe.db.get_value("Account", {"company": COMPANY, "account_number": number}, "name")
	if existing:
		return existing

	root = frappe.get_all(
		"Account",
		filters={"company": COMPANY, "root_type": root_type, "is_group": 1},
		order_by="lft asc",
		limit=1,
	)[0].name

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"company": COMPANY,
			"account_name": name,
			"account_number": number,
			"parent_account": root,
			"root_type": root_type,
			"account_type": account_type or None,
			"account_currency": "EUR",
			"is_group": 0,
		}
	)
	if account_type == "Tax":
		doc.tax_rate = 19.0
	doc.insert()
	return doc.name


def create_party(doctype: str, name: str, tax_id: str) -> None:
	if not frappe.db.exists(doctype, name):
		party = frappe.get_doc(
			{
				"doctype": doctype,
				f"{doctype.lower()}_name": name,
				f"{doctype.lower()}_type": "Company",
				"tax_id": tax_id,
			}
		)
		party.insert()

	if frappe.db.exists("Address", {"address_title": name}):
		return

	frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": name,
			"address_type": "Billing",
			"address_line1": "Musterstraße 1",
			"city": "Berlin",
			"pincode": "10115",
			"country": "Germany",
			"is_primary_address": 1,
			"links": [{"link_doctype": doctype, "link_name": name}],
		}
	).insert()


def create_bookings(accounts: dict[str, str]) -> None:
	if frappe.db.exists("Journal Entry", {"company": COMPANY, "user_remark": "Testbuchung GDPdU Erlös"}):
		return

	sales = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": COMPANY,
			"posting_date": nowdate(),
			"user_remark": "Testbuchung GDPdU Erlös",
			"accounts": [
				{
					"account": accounts["1400"],
					"party_type": "Customer",
					"party": CUSTOMER,
					"debit_in_account_currency": 1190,
				},
				{"account": accounts["8400"], "credit_in_account_currency": 1000},
				{"account": accounts["1776"], "credit_in_account_currency": 190},
			],
		}
	)
	sales.insert()
	sales.submit()

	purchase = frappe.get_doc(
		{
			"doctype": "Journal Entry",
			"voucher_type": "Journal Entry",
			"company": COMPANY,
			"posting_date": nowdate(),
			"user_remark": "Testbuchung GDPdU Aufwand",
			"accounts": [
				{"account": accounts["4980"], "debit_in_account_currency": 100},
				{
					"account": accounts["1600"],
					"party_type": "Supplier",
					"party": SUPPLIER,
					"credit_in_account_currency": 100,
				},
			],
		}
	)
	purchase.insert()
	purchase.submit()
