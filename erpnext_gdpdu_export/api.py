"""Whitelisted module functions: everything the app can do, callable without the form.

Frappe 16 maps these to ``/api/v2/method/erpnext_gdpdu_export.api.<function>`` and
the native MCP server exposes them as tools. All functions return plain data;
permission checks are the same as in the Desk (DocType permissions of
*GDPdU Export* and *GDPdU Company Settings*).

Every function takes the company explicitly: the default company of the settings
is a form default, never a silent assumption of the API.
"""

from __future__ import annotations

import frappe
from frappe.utils import cint, getdate, nowdate

from erpnext_gdpdu_export import __version__
from erpnext_gdpdu_export.gdpdu.dtd import SOURCE_BUNDLED, SOURCE_SETTINGS, get_dtd
from erpnext_gdpdu_export.gdpdu.index_xml import DTD_FILE_NAME
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings.gdpdu_company_settings import (
	ensure_company_settings,
	get_company_settings,
)
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export import (
	BUSY_STATES,
	FINISHED_STATES,
	PERIOD_CUSTOM,
	PERIOD_FISCAL_YEAR,
	STATUS_COMPLETED,
	STATUS_FAILED,
)

EXPORT_DOCTYPE = "GDPdU Export"
SETTINGS_DOCTYPE = "GDPdU Company Settings"

OVERVIEW_FIELDS = [
	"name",
	"period_type",
	"fiscal_year",
	"from_date",
	"to_date",
	"status",
	"export_file",
	"package_name",
	"journal_rows",
	"dtd_included",
	"error_message",
	"started_at",
	"finished_at",
	"owner",
	"modified",
]


# ------------------------------------------------------------------- exports


@frappe.whitelist()
def create_export(
	company: str,
	fiscal_year: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	start: bool | int | str = False,
) -> dict:
	"""Create an export document for ``company``; with ``start`` also queue the job.

	Either ``fiscal_year`` (period taken from the fiscal year) or both dates.
	"""
	frappe.has_permission(EXPORT_DOCTYPE, "create", throw=True)
	_require_company(company)

	if not fiscal_year and not (from_date and to_date):
		frappe.throw("Bitte geben Sie entweder das Geschäftsjahr oder das Von- und Bis-Datum an.")

	doc = frappe.get_doc(
		{
			"doctype": EXPORT_DOCTYPE,
			"company": company,
			"period_type": PERIOD_FISCAL_YEAR if fiscal_year else PERIOD_CUSTOM,
			"fiscal_year": fiscal_year,
			"from_date": from_date,
			"to_date": to_date,
		}
	).insert()

	result = {"created": True, "started": False, **doc.get_status()}
	if cint(start):
		result.update(doc.start_export())
		result["started"] = True
	return result


@frappe.whitelist()
def start_export(name: str) -> dict:
	"""Queue the background job of an existing export."""
	return frappe.get_doc(EXPORT_DOCTYPE, name).start_export()


@frappe.whitelist()
def get_export_status(name: str) -> dict:
	"""Read-only status of one export, including the protocol of the last run."""
	return frappe.get_doc(EXPORT_DOCTYPE, name).get_status()


@frappe.whitelist()
def verify_export(name: str) -> dict:
	"""Re-check the attached package of one export (files present, index.xml valid)."""
	return frappe.get_doc(EXPORT_DOCTYPE, name).verify_package()


@frappe.whitelist()
def list_exports(company: str, limit: int = 20, status: str | None = None) -> list[dict]:
	"""The exports of one company, newest first."""
	frappe.has_permission(EXPORT_DOCTYPE, "read", throw=True)
	_require_company(company)

	filters = {"company": company}
	if status:
		filters["status"] = status

	return frappe.get_all(
		EXPORT_DOCTYPE,
		filters=filters,
		fields=OVERVIEW_FIELDS,
		order_by="creation desc",
		limit=cint(limit) or 20,
	)


@frappe.whitelist()
def download_package(name: str):
	"""Stream the ZIP of a finished export (REST: the response body is the file)."""
	doc = frappe.get_doc(EXPORT_DOCTYPE, name)
	doc.check_permission("read")
	if not doc.export_file:
		frappe.throw("Es ist kein Export-Paket hinterlegt. Bitte erstellen Sie den Export zuerst.")

	from erpnext_gdpdu_export.gdpdu.dtd import read_attachment_bytes

	file_doc = frappe.get_doc("File", {"file_url": doc.export_file})
	frappe.response.filename = doc.package_name or file_doc.file_name
	frappe.response.filecontent = read_attachment_bytes(file_doc)
	frappe.response.type = "download"


@frappe.whitelist()
def delete_old_exports(
	company: str,
	keep: int | str | None = None,
	older_than_days: int | str | None = None,
	dry_run: bool | int | str = False,
) -> dict:
	"""Delete finished exports of ``company`` and their packages.

	``keep``: how many of the newest finished exports stay (default: the company's
	setting *Fertige Exporte aufbewahren*). ``older_than_days``: additionally only
	exports finished before that many days ago. Running exports are never touched.
	With ``dry_run`` nothing is deleted, the result only lists the candidates.
	"""
	frappe.has_permission(EXPORT_DOCTYPE, "delete", throw=True)
	_require_company(company)

	settings = get_company_settings(company)
	keep = cint(keep) if keep not in (None, "") else settings.keep_last_exports
	older_than_days = cint(older_than_days) if older_than_days not in (None, "") else None

	if keep <= 0 and older_than_days is None:
		frappe.throw(
			"Bitte geben Sie an, wie viele Exporte behalten werden sollen (keep) oder ab welchem Alter "
			"gelöscht wird (older_than_days), oder hinterlegen Sie „Fertige Exporte aufbewahren“ in den "
			"Unternehmenseinstellungen."
		)

	finished = frappe.get_all(
		EXPORT_DOCTYPE,
		filters={"company": company, "status": ("in", FINISHED_STATES)},
		fields=["name", "status", "finished_at", "modified", "package_name"],
	)
	# Frappe 16 refuses SQL functions in order_by; sort in Python instead.
	finished.sort(key=lambda row: row.finished_at or row.modified, reverse=True)

	candidates = finished[keep:] if keep > 0 else finished
	if older_than_days is not None:
		cutoff = frappe.utils.add_days(nowdate(), -older_than_days)
		candidates = [row for row in candidates if getdate(row.finished_at or row.modified) < getdate(cutoff)]

	deleted = []
	for row in candidates:
		if not cint(dry_run):
			frappe.delete_doc(EXPORT_DOCTYPE, row.name)
		deleted.append({"name": row.name, "status": row.status, "package_name": row.package_name})

	return {
		"company": company,
		"dry_run": bool(cint(dry_run)),
		"kept": keep,
		"older_than_days": older_than_days,
		"finished_exports": len(finished),
		"deleted": deleted,
		"deleted_count": len(deleted),
	}


# ----------------------------------------------------------------- overview


@frappe.whitelist()
def company_overview(company: str, limit: int = 10) -> dict:
	"""Everything an assistant needs to judge the state of one company's exports."""
	frappe.has_permission(EXPORT_DOCTYPE, "read", throw=True)
	_require_company(company)

	settings = get_company_settings(company)
	exports = list_exports(company, limit=limit)
	counts: dict = {}
	for row in frappe.get_all(EXPORT_DOCTYPE, filters={"company": company}, fields=["status"]):
		counts[row.status] = counts.get(row.status, 0) + 1
	latest_completed = next((row for row in exports if row.status == STATUS_COMPLETED), None)
	dtd = get_dtd_status()

	problems = []
	if not settings.exists:
		problems.append(
			{
				"code": "missing_company_settings",
				"message": f"Für {company} gibt es noch keinen Datensatz GDPdU Company Settings.",
				"hint": (
					"Anlegen (create_company_settings); bis dahin werden die Stammdaten des "
					"Unternehmens verwendet."
				),
			}
		)
	if not settings.tax_id:
		problems.append(
			{
				"code": "missing_tax_id",
				"message": f"Für {company} ist keine Steuernummer hinterlegt.",
				"hint": "Steuernummer in den GDPdU Company Settings eintragen.",
			}
		)
	if not dtd["available"]:
		problems.append(
			{
				"code": "missing_dtd",
				"message": f"Die Datei {DTD_FILE_NAME} ist nicht hinterlegt; Pakete sind unvollständig.",
				"hint": "DTD einmalig in den GDPdU Export Settings hochladen.",
			}
		)
	for row in exports:
		if row.status == STATUS_FAILED:
			problems.append(
				{
					"code": "failed_export",
					"message": f"Export {row.name} ist fehlgeschlagen: {row.error_message or ''}".strip(),
					"hint": "Fehlermeldung prüfen und den Export erneut starten (start_export).",
				}
			)
		elif row.status in BUSY_STATES:
			problems.append(
				{
					"code": "running_export",
					"message": f"Export {row.name} ist im Zustand {row.status}.",
					"hint": (
						"Status später erneut abfragen; bleibt er hängen: bench doctor und die "
						"Queue long prüfen."
					),
				}
			)

	if latest_completed:
		warnings = (
			frappe.get_doc(EXPORT_DOCTYPE, latest_completed.name).protocol_summary().get("warnings", [])
		)
		for warning in warnings:
			problems.append(
				{
					"code": f"protocol_{warning.get('code')}",
					"message": f"Letzter Export {latest_completed.name}: {warning.get('message')}",
					"hint": warning.get("hint", ""),
				}
			)

	return {
		"company": company,
		"app_version": __version__,
		"settings": settings.as_dict(),
		"dtd": dtd,
		"fiscal_years": fiscal_years_for_company(company),
		"export_counts": counts,
		"latest_completed_export": latest_completed,
		"exports": exports,
		"problems": problems,
	}


@frappe.whitelist()
def fiscal_years_for_company(company: str) -> list[dict]:
	"""Fiscal years usable for ``company`` (unrestricted ones plus those naming the company)."""
	_require_company(company)
	years = frappe.get_all(
		"Fiscal Year",
		filters={"disabled": 0},
		fields=["name", "year_start_date", "year_end_date"],
		order_by="year_start_date desc",
	)
	restrictions = frappe.get_all("Fiscal Year Company", fields=["parent", "company"])
	restricted: dict[str, set[str]] = {}
	for row in restrictions:
		restricted.setdefault(row.parent, set()).add(row.company)

	return [
		{
			"name": year.name,
			"from_date": year.year_start_date,
			"to_date": year.year_end_date,
			"closed": getdate(year.year_end_date) < getdate(nowdate()),
		}
		for year in years
		if year.name not in restricted or company in restricted[year.name]
	]


# ----------------------------------------------------------------- settings


@frappe.whitelist()
def get_company_settings_status(company: str) -> dict:
	"""Resolved settings of one company including fallbacks from the Company record."""
	frappe.has_permission(SETTINGS_DOCTYPE, "read", throw=True)
	return get_company_settings(company).as_dict()


@frappe.whitelist()
def create_company_settings(company: str) -> dict:
	"""Create the settings record of ``company`` from its master data if it is missing."""
	frappe.has_permission(SETTINGS_DOCTYPE, "create", throw=True)
	_require_company(company)
	name = ensure_company_settings(company)
	return {"name": name, **get_company_settings(company).as_dict()}


@frappe.whitelist()
def get_dtd_status() -> dict:
	"""Whether the Audicon DTD is available and where it comes from."""
	frappe.has_permission("GDPdU Export Settings", "read", throw=True)
	result = get_dtd()
	labels = {SOURCE_SETTINGS: "GDPdU Export Settings", SOURCE_BUNDLED: "resources/ im App-Ordner"}
	return {
		"available": bool(result.content),
		"source": result.source,
		"source_label": labels.get(result.source or "", ""),
		"file_name": DTD_FILE_NAME,
		"size": len(result.content) if result.content else 0,
	}


@frappe.whitelist()
def list_companies() -> list[dict]:
	"""Companies the user may export, with the state of their settings record."""
	frappe.has_permission(EXPORT_DOCTYPE, "read", throw=True)
	configured = set(frappe.get_all(SETTINGS_DOCTYPE, pluck="company"))
	default_company = frappe.db.get_single_value("GDPdU Export Settings", "default_company")
	return [
		{
			"company": row.name,
			"company_name": row.company_name,
			"abbr": row.abbr,
			"currency": row.default_currency,
			"has_settings": row.name in configured,
			"is_default": row.name == default_company,
		}
		for row in frappe.get_all(
			"Company", fields=["name", "company_name", "abbr", "default_currency"], order_by="name"
		)
	]


# ------------------------------------------------------------------ helpers


def _require_company(company: str | None) -> None:
	if not company:
		frappe.throw("Bitte geben Sie das Unternehmen an (company).")
	if not frappe.db.exists("Company", company):
		frappe.throw(f"Das Unternehmen {company} existiert nicht.")
