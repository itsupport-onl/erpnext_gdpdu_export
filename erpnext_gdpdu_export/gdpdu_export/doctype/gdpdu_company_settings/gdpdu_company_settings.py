"""Per-company settings of the GDPdU export.

One record per company. Everything that differs between two companies on the
same site lives here (data supplier of the index.xml, tax number, consultant
numbers, defaults); what is the same for the whole site stays in the single
*GDPdU Export Settings*.

The export works without a record: :func:`get_company_settings` then falls back
to the master data of the company, so a fresh installation needs no manual step.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import frappe
from frappe.model.document import Document
from frappe.utils import cint

from erpnext_gdpdu_export.gdpdu_export.explicit_company import ExplicitCompanyMixin

PERIOD_FISCAL_YEAR = "Geschäftsjahr"

TEXT_FIELDS = ("supplier_name", "supplier_location", "tax_id", "consultant_number", "client_number")


@dataclass
class CompanySettings:
	"""Resolved settings of one company: record values with master-data fallbacks."""

	company: str
	exists: bool
	supplier_name: str
	supplier_location: str
	tax_id: str
	chart_of_accounts: str
	consultant_number: str
	client_number: str
	supplier_comment: str
	default_period_type: str
	keep_last_exports: int

	def as_dict(self) -> dict:
		return asdict(self)


class GDPdUCompanySettings(ExplicitCompanyMixin, Document):
	def validate(self):
		self.require_company()
		self.keep_last_exports = max(cint(self.keep_last_exports), 0)
		for fieldname in TEXT_FIELDS:
			value = self.get(fieldname)
			if value:
				self.set(fieldname, value.strip())
		self.validate_tax_exempt_accounts()

	def validate_tax_exempt_accounts(self):
		"""Only tax accounts of this company can be declared as genuine 0 % accounts."""
		seen = set()
		for row in list(self.get("tax_exempt_accounts") or []):
			if row.account in seen:
				self.remove(row)
				continue
			seen.add(row.account)
			account = frappe.db.get_value(
				"Account", row.account, ["company", "account_type", "is_group"], as_dict=True
			)
			if not account or account.company != self.company:
				frappe.throw(f"Das Konto {row.account} gehört nicht zum Unternehmen {self.company}.")
			if account.account_type != "Tax" or account.is_group:
				frappe.throw(
					f"Das Konto {row.account} ist kein Steuerkonto (Kontoart „Tax“, keine Kontengruppe)."
				)

	@frappe.whitelist()
	def status(self) -> dict:
		"""Resolved settings including the fallbacks the export would use."""
		self.check_permission("read")
		return get_company_settings(self.company).as_dict()

	@frappe.whitelist()
	def overview(self, limit: int = 10) -> dict:
		"""Latest exports, periods, files and problems of this company."""
		from erpnext_gdpdu_export.api import company_overview

		return company_overview(self.company, limit=limit)


def get_company_settings(company: str) -> CompanySettings:
	"""Return the settings of ``company``; missing values come from the Company record."""
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(f"Das Unternehmen {company} existiert nicht.")

	company_doc = frappe.get_cached_doc("Company", company)
	record = None
	record_name = frappe.db.get_value("GDPdU Company Settings", {"company": company}, "name")
	if record_name:
		record = frappe.get_doc("GDPdU Company Settings", record_name)

	def value(fieldname: str, fallback: str = "") -> str:
		raw = (record.get(fieldname) if record else None) or fallback or ""
		return str(raw).strip()

	return CompanySettings(
		company=company,
		exists=record is not None,
		supplier_name=value("supplier_name", company_doc.company_name or company),
		supplier_location=value("supplier_location", company_location(company) or company_doc.country or ""),
		tax_id=value("tax_id", company_doc.get("tax_id") or ""),
		chart_of_accounts=value("chart_of_accounts", company_doc.get("chart_of_accounts") or ""),
		consultant_number=value("consultant_number"),
		client_number=value("client_number"),
		supplier_comment=value("supplier_comment"),
		default_period_type=value("default_period_type", PERIOD_FISCAL_YEAR),
		keep_last_exports=int((record.keep_last_exports if record else 0) or 0),
	)


def company_location(company: str) -> str:
	"""City of the company address: ``<Location>`` of the data supplier."""
	rows = frappe.db.sql(
		"""
		SELECT address.city
		FROM `tabAddress` address
		INNER JOIN `tabDynamic Link` link
			ON link.parent = address.name AND link.parenttype = 'Address'
		WHERE link.link_doctype = 'Company' AND link.link_name = %(company)s
		ORDER BY IFNULL(address.is_primary_address, 0) DESC, address.creation ASC
		LIMIT 1
		""",
		{"company": company},
		as_dict=True,
	)
	return (rows[0].city if rows else "") or ""


def ensure_company_settings(company: str) -> str:
	"""Create the settings record of ``company`` from its master data if it is missing.

	Used by the migration patch and by the API, so a company never needs a manual
	step before its first export. Returns the record name.
	"""
	existing = frappe.db.get_value("GDPdU Company Settings", {"company": company}, "name")
	if existing:
		return existing

	resolved = get_company_settings(company)
	doc = frappe.get_doc(
		{
			"doctype": "GDPdU Company Settings",
			"company": company,
			"supplier_name": resolved.supplier_name,
			"supplier_location": resolved.supplier_location,
			"tax_id": resolved.tax_id,
			"chart_of_accounts": resolved.chart_of_accounts,
			"default_period_type": PERIOD_FISCAL_YEAR,
			"keep_last_exports": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def create_for_new_company(doc, method=None) -> None:
	"""``doc_events`` hook *Company* ``after_insert``: settings record for a new company.

	The patch of 0.3.0 covers the companies that existed at the update; this hook covers
	every company created later, so each one has its record from the start. The record
	names the new company explicitly. A failure must never block the creation of the
	company itself: the export falls back to the master data anyway, and
	``company_overview`` reports the missing record.
	"""
	savepoint = "gdpdu_company_settings"
	frappe.db.savepoint(savepoint)
	try:
		ensure_company_settings(doc.name)
	except Exception:
		frappe.db.rollback(save_point=savepoint)
		frappe.log_error(
			title=f"GDPdU Company Settings für {doc.name} nicht angelegt",
			message=frappe.get_traceback(),
		)
