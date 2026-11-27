"""Two companies on one site: every export belongs to exactly one of them.

Needs a site: ``bench --site <site> run-tests --app erpnext_gdpdu_export``.

Reuses the fixtures of the GDPdU Export tests for the first company and adds a
second company with its own accounts, parties and bookings. The second company
deliberately uses different account numbers and names, so a row of the wrong
company would be visible in any exported table.
"""

from __future__ import annotations

import csv
import io
import zipfile
from unittest import mock

import frappe
from frappe.utils import nowdate

from erpnext_gdpdu_export.gdpdu.index_xml import INDEX_FILE_NAME
from erpnext_gdpdu_export.gdpdu.package import PROTOCOL_FILE_NAME, README_FILE_NAME, build_package
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings.gdpdu_company_settings import (
	ensure_company_settings,
	get_company_settings,
)
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.test_gdpdu_export import (
	COMPANY,
	CUSTOMER,
	SUPPLIER,
	create_account,
	create_bookings,
	create_company,
	create_fixtures,
	create_party,
)
from erpnext_gdpdu_export.patches.v0_3 import create_company_settings as patch
from erpnext_gdpdu_export.tests.base import LEGACY_TEST_RUNNER, AppTestCase

IGNORE_TEST_RECORD_DEPENDENCIES = ["Company"]

if LEGACY_TEST_RUNNER:
	test_ignore = IGNORE_TEST_RECORD_DEPENDENCIES

#: A company created after the installation (ERP-087).
LATE_COMPANY = "_Test GDPdU Neugründung GmbH"
LATE_COMPANY_ABBR = "TGDN"

#: The second company: a subsidiary audited separately from the first one.
SUBSIDIARY = "_Test GDPdU Tochter UG"
SUBSIDIARY_ABBR = "TGDT"
SUBSIDIARY_CUSTOMER = "_Test GDPdU Kundin Tochter"
SUBSIDIARY_SUPPLIER = "_Test GDPdU Lieferant Tochter"
SUBSIDIARY_SUPPLIER_NAME = "todo.monster Tochter UG (haftungsbeschränkt)"
SUBSIDIARY_TAX_ID = "30/123/45678"
SUBSIDIARY_CLIENT_NUMBER = "4711"

#: Logical key of the fixtures -> account of the subsidiary (own numbers and names).
SUBSIDIARY_ACCOUNTS = {
	"1200": ("7200", "Bank Tochter", "Asset", "Bank"),
	"1400": ("7400", "Forderungen Tochter", "Asset", "Receivable"),
	"1600": ("7600", "Verbindlichkeiten Tochter", "Liability", "Payable"),
	"1776": ("7776", "Umsatzsteuer Tochter", "Liability", "Tax"),
	"4980": ("7980", "Bürobedarf Tochter", "Expense", ""),
	"8400": ("7840", "Erlöse Tochter", "Income", ""),
}


class TestGDPdUCompanySettings(AppTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.year = int(nowdate()[:4])
		cls.from_date = f"{cls.year}-01-01"
		cls.to_date = f"{cls.year}-12-31"
		create_fixtures()
		create_subsidiary_fixtures()
		frappe.db.commit()

	def setUp(self):
		ensure_company_settings(COMPANY)
		settings = frappe.get_doc("GDPdU Company Settings", ensure_company_settings(SUBSIDIARY))
		settings.update(
			{
				"supplier_name": SUBSIDIARY_SUPPLIER_NAME,
				"tax_id": SUBSIDIARY_TAX_ID,
				"client_number": SUBSIDIARY_CLIENT_NUMBER,
				"chart_of_accounts": "SKR03",
			}
		)
		settings.save()

	def build(self, company: str):
		return build_package(company, self.from_date, self.to_date)

	def read_package(self, result) -> dict[str, bytes]:
		with zipfile.ZipFile(io.BytesIO(result.content)) as archive:
			return {name: archive.read(name) for name in archive.namelist()}

	def read_csv(self, files: dict[str, bytes], filename: str) -> list[dict]:
		content = files[filename].decode("utf-8")
		reader = csv.DictReader(io.StringIO(content, newline=""), delimiter=";", quotechar='"')
		return list(reader)

	# ------------------------------------------------------------ isolation

	def test_journal_of_one_company_holds_only_its_own_entries(self):
		for company, other in ((COMPANY, SUBSIDIARY), (SUBSIDIARY, COMPANY)):
			files = self.read_package(self.build(company))
			rows = self.read_csv(files, "journal.csv")

			expected = frappe.get_all(
				"GL Entry",
				filters={
					"company": company,
					"is_cancelled": 0,
					"posting_date": ("between", [self.from_date, self.to_date]),
				},
				pluck="name",
			)
			self.assertTrue(rows, company)
			self.assertEqual(sorted(row["JournalID"] for row in rows), sorted(expected))

			foreign = set(frappe.get_all("GL Entry", filters={"company": other}, pluck="name"))
			self.assertFalse(foreign & {row["JournalID"] for row in rows}, f"{other} rows in {company}")

	def test_chart_of_accounts_and_tax_codes_belong_to_the_company(self):
		files = self.read_package(self.build(COMPANY))
		parent_keys = {row["Konto"] for row in self.read_csv(files, "kontenplan.csv")}
		parent_taxes = {row["Steuerkonto"] for row in self.read_csv(files, "steuerkennzeichen.csv")}

		files = self.read_package(self.build(SUBSIDIARY))
		child_keys = {row["Konto"] for row in self.read_csv(files, "kontenplan.csv")}
		child_taxes = {row["Steuerkonto"] for row in self.read_csv(files, "steuerkennzeichen.csv")}

		self.assertIn("8400", parent_keys)
		self.assertIn("7840", child_keys)
		self.assertNotIn("7840", parent_keys)
		self.assertNotIn("8400", child_keys)
		# Both companies also carry the standard tax accounts of their chart; only
		# the numbered test accounts tell them apart.
		self.assertIn("1776", parent_taxes)
		self.assertNotIn("7776", parent_taxes)
		self.assertIn("7776", child_taxes)
		self.assertNotIn("1776", child_taxes)

	def test_parties_and_open_items_belong_to_the_company(self):
		files = self.read_package(self.build(SUBSIDIARY))

		customers = [row["Kennung"] for row in self.read_csv(files, "debitoren.csv")]
		suppliers = [row["Kennung"] for row in self.read_csv(files, "kreditoren.csv")]
		self.assertEqual(customers, [SUBSIDIARY_CUSTOMER])
		self.assertEqual(suppliers, [SUBSIDIARY_SUPPLIER])
		self.assertNotIn(CUSTOMER, customers)
		self.assertNotIn(SUPPLIER, suppliers)

		open_parties = {row["Partei"] for row in self.read_csv(files, "opos_debitoren.csv")}
		self.assertEqual(open_parties, {SUBSIDIARY_CUSTOMER})
		open_accounts = {row["Konto"] for row in self.read_csv(files, "opos_debitoren.csv")}
		self.assertEqual(open_accounts, {"7400"})

		# The parent company's invoices, payments and assets never show up here.
		for filename in (
			"ausgangsrechnungen.csv",
			"eingangsrechnungen.csv",
			"zahlungen.csv",
			"anlagegueter.csv",
		):
			self.assertEqual(self.read_csv(files, filename), [], filename)

	def test_sums_are_computed_per_company(self):
		parent = self.build(COMPANY).protocol
		child = self.build(SUBSIDIARY).protocol

		self.assertTrue(parent.is_balanced)
		self.assertTrue(child.is_balanced)
		self.assertNotEqual(parent.total_debit, child.total_debit)
		self.assertGreater(parent.journal_rows, child.journal_rows)

	# ------------------------------------------------------- description

	def test_index_xml_names_the_exported_company(self):
		files = self.read_package(self.build(SUBSIDIARY))
		index = files[INDEX_FILE_NAME].decode("utf-8")

		self.assertIn(f"<Name>{SUBSIDIARY_SUPPLIER_NAME}</Name>", index)
		self.assertIn(f"Steuernummer {SUBSIDIARY_TAX_ID}", index)
		self.assertIn(f"Mandantennummer {SUBSIDIARY_CLIENT_NUMBER}", index)
		self.assertNotIn(COMPANY, index)

		protocol = files[PROTOCOL_FILE_NAME].decode("utf-8")
		self.assertIn(f"Unternehmen:      {SUBSIDIARY_SUPPLIER_NAME}", protocol)
		self.assertIn(SUBSIDIARY_TAX_ID, protocol)
		self.assertIn("SKR03", protocol)

		readme = files[README_FILE_NAME].decode("utf-8")
		self.assertIn(SUBSIDIARY_SUPPLIER_NAME, readme)
		self.assertIn(SUBSIDIARY_TAX_ID, readme)

	def test_index_xml_of_the_parent_does_not_carry_the_subsidiary(self):
		files = self.read_package(self.build(COMPANY))
		index = files[INDEX_FILE_NAME].decode("utf-8")

		self.assertIn(f"<Name>{COMPANY}</Name>", index)
		self.assertNotIn(SUBSIDIARY_SUPPLIER_NAME, index)
		self.assertNotIn(SUBSIDIARY_TAX_ID, index)

	def test_package_name_uses_the_company_abbreviation(self):
		self.assertIn(f"_{SUBSIDIARY_ABBR}_", self.build(SUBSIDIARY).file_name)
		self.assertNotIn(f"_{SUBSIDIARY_ABBR}_", self.build(COMPANY).file_name)

	def test_protocol_dict_carries_the_company_details(self):
		data = self.build(SUBSIDIARY).protocol.as_dict()

		self.assertEqual(data["company"], SUBSIDIARY_SUPPLIER_NAME)
		self.assertEqual(data["tax_id"], SUBSIDIARY_TAX_ID)
		self.assertEqual(data["client_number"], SUBSIDIARY_CLIENT_NUMBER)
		self.assertTrue(data["is_balanced"])
		self.assertEqual([t["filename"] for t in data["tables"]][0], "journal.csv")

	# --------------------------------------------------------------- settings

	def test_settings_fall_back_to_the_company_master_data(self):
		frappe.delete_doc("GDPdU Company Settings", SUBSIDIARY, force=True)

		settings = get_company_settings(SUBSIDIARY)
		self.assertFalse(settings.exists)
		self.assertEqual(settings.supplier_name, SUBSIDIARY)
		self.assertEqual(settings.tax_id, "")
		self.assertEqual(settings.keep_last_exports, 0)

		# The export still works and names the company itself.
		files = self.read_package(self.build(SUBSIDIARY))
		self.assertIn(f"<Name>{SUBSIDIARY}</Name>", files[INDEX_FILE_NAME].decode("utf-8"))

	def test_one_record_per_company(self):
		duplicate = frappe.get_doc({"doctype": "GDPdU Company Settings", "company": SUBSIDIARY})
		self.assertRaises(frappe.DuplicateEntryError, duplicate.insert)

	def test_status_resolves_values_and_fallbacks(self):
		doc = frappe.get_doc("GDPdU Company Settings", SUBSIDIARY)
		doc.supplier_location = ""
		doc.save()

		status = doc.status()
		self.assertTrue(status["exists"])
		self.assertEqual(status["supplier_name"], SUBSIDIARY_SUPPLIER_NAME)
		self.assertEqual(status["supplier_location"], "Germany")

	def test_default_period_type_is_resolved_per_company(self):
		# The form reads this value for new exports of the company (gdpdu_export.js).
		doc = frappe.get_doc("GDPdU Company Settings", SUBSIDIARY)
		doc.default_period_type = "Benutzerdefiniert"
		doc.save()

		self.assertEqual(get_company_settings(SUBSIDIARY).default_period_type, "Benutzerdefiniert")
		self.assertEqual(get_company_settings(COMPANY).default_period_type, "Geschäftsjahr")

	# ------------------------------------------------------------------ patch

	def test_patch_creates_a_record_for_every_company(self):
		frappe.delete_doc("GDPdU Company Settings", COMPANY, force=True)
		frappe.delete_doc("GDPdU Company Settings", SUBSIDIARY, force=True)
		frappe.db.set_value("Company", SUBSIDIARY, "tax_id", "99/999/99999")

		patch.execute()

		for company in (COMPANY, SUBSIDIARY):
			self.assertTrue(frappe.db.exists("GDPdU Company Settings", company), company)

		created = frappe.get_doc("GDPdU Company Settings", SUBSIDIARY)
		self.assertEqual(created.supplier_name, SUBSIDIARY)
		self.assertEqual(created.tax_id, "99/999/99999")
		self.assertEqual(created.default_period_type, "Geschäftsjahr")

		# Running the patch again changes nothing that was maintained in between.
		created.tax_id = SUBSIDIARY_TAX_ID
		created.save()
		patch.execute()
		kept = frappe.db.get_value("GDPdU Company Settings", SUBSIDIARY, "tax_id")
		self.assertEqual(kept, SUBSIDIARY_TAX_ID)
		frappe.db.set_value("Company", SUBSIDIARY, "tax_id", None)

	# ----------------------------------------------------- new companies

	def test_company_created_later_gets_its_record(self):
		"""ERP-087: the Company hook creates the record, naming the company explicitly."""
		handlers = frappe.get_hooks("doc_events").get("Company", {}).get("after_insert", [])
		self.assertIn(
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings."
			"gdpdu_company_settings.create_for_new_company",
			handlers,
		)

		if frappe.db.exists("Company", LATE_COMPANY):
			# A previous run created the company already: drop its record and run the
			# after_insert handlers the way Frappe runs them for a new company.
			frappe.delete_doc("GDPdU Company Settings", LATE_COMPANY, force=True, ignore_missing=True)
			company = frappe.get_doc("Company", LATE_COMPANY)
			for handler in handlers:
				frappe.get_attr(handler)(company, "after_insert")
		else:
			create_company(LATE_COMPANY, LATE_COMPANY_ABBR)

		record = frappe.db.get_value(
			"GDPdU Company Settings", {"company": LATE_COMPANY}, ["name", "company", "supplier_name"]
		)
		self.assertIsNotNone(record)
		self.assertEqual(record[1], LATE_COMPANY)
		self.assertEqual(record[2], LATE_COMPANY)

	def test_failing_record_does_not_block_the_company(self):
		from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings import (
			gdpdu_company_settings as module,
		)

		company = frappe.get_doc("Company", SUBSIDIARY)
		with mock.patch.object(module, "ensure_company_settings", side_effect=frappe.ValidationError):
			module.create_for_new_company(company, "after_insert")

		self.assertTrue(
			frappe.db.exists("Error Log", {"method": f"GDPdU Company Settings für {SUBSIDIARY} nicht angelegt"})
		)

	# --------------------------------------------------------- fiscal years

	def test_fiscal_year_restricted_to_another_company_is_rejected(self):
		fiscal_year = create_restricted_fiscal_year(SUBSIDIARY, self.year - 15)

		foreign = frappe.get_doc(
			{
				"doctype": "GDPdU Export",
				"company": COMPANY,
				"period_type": "Geschäftsjahr",
				"fiscal_year": fiscal_year,
			}
		)
		self.assertRaises(frappe.ValidationError, foreign.insert)

		own = frappe.get_doc(
			{
				"doctype": "GDPdU Export",
				"company": SUBSIDIARY,
				"period_type": "Geschäftsjahr",
				"fiscal_year": fiscal_year,
			}
		).insert()
		self.assertEqual(str(own.from_date), f"{self.year - 15}-01-01")
		own.delete()


# ---------------------------------------------------------------- fixtures


def create_subsidiary_fixtures() -> dict[str, str]:
	create_company(SUBSIDIARY, SUBSIDIARY_ABBR)
	accounts = {key: create_account(row, SUBSIDIARY) for key, row in SUBSIDIARY_ACCOUNTS.items()}
	create_party("Customer", SUBSIDIARY_CUSTOMER, "DE111222333")
	create_party("Supplier", SUBSIDIARY_SUPPLIER, "DE444555666")
	create_bookings(
		accounts,
		company=SUBSIDIARY,
		customer=SUBSIDIARY_CUSTOMER,
		supplier=SUBSIDIARY_SUPPLIER,
		remark="Testbuchung GDPdU Tochter",
	)
	return accounts


def create_restricted_fiscal_year(company: str, year: int) -> str:
	"""A fiscal year that is valid for ``company`` only."""
	name = f"_Test GDPdU {year} {company}"
	if frappe.db.exists("Fiscal Year", name):
		return name

	return (
		frappe.get_doc(
			{
				"doctype": "Fiscal Year",
				"year": name,
				"year_start_date": f"{year}-01-01",
				"year_end_date": f"{year}-12-31",
				"companies": [{"company": company}],
			}
		)
		.insert()
		.name
	)
