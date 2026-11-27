"""Controller of the GDPdU Export document.

The document only collects the user's choices and shows the result; the actual
package is built in a background job so large journals cannot run into a
request timeout.

Every action is a whitelisted method that returns plain data, so the form, the
REST API and the MCP server of Frappe 16 all drive the same code.
"""

from __future__ import annotations

import io
import json
import zipfile

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from erpnext_gdpdu_export.gdpdu.dtd import get_dtd, read_attachment_bytes, validate_index_xml
from erpnext_gdpdu_export.gdpdu.index_xml import DTD_FILE_NAME, INDEX_FILE_NAME
from erpnext_gdpdu_export.gdpdu.package import PROTOCOL_FILE_NAME, README_FILE_NAME, build_package
from erpnext_gdpdu_export.gdpdu.schema import get_tables
from erpnext_gdpdu_export.gdpdu_export.explicit_company import ExplicitCompanyMixin

STATUS_DRAFT = "Entwurf"
STATUS_QUEUED = "In Warteschlange"
STATUS_RUNNING = "Läuft"
STATUS_COMPLETED = "Fertig"
STATUS_FAILED = "Fehlgeschlagen"

BUSY_STATES = (STATUS_QUEUED, STATUS_RUNNING)
FINISHED_STATES = (STATUS_COMPLETED, STATUS_FAILED)

PERIOD_FISCAL_YEAR = "Geschäftsjahr"
PERIOD_CUSTOM = "Benutzerdefiniert"

#: Sent to the browser so the form can refresh itself when the job is done.
REALTIME_EVENT = "gdpdu_export_update"

JOB_TIMEOUT = 4 * 60 * 60

EXPORT_FIELDS = (
	"name",
	"company",
	"period_type",
	"fiscal_year",
	"from_date",
	"to_date",
	"status",
	"export_file",
	"package_name",
	"error_message",
	"started_at",
	"finished_at",
	"journal_rows",
	"dtd_included",
	"app_version",
	"owner",
	"creation",
	"modified",
)


class GDPdUExport(ExplicitCompanyMixin, Document):
	def validate(self):
		self.require_company()
		self.apply_fiscal_year()
		self.validate_fiscal_year_company()
		self.validate_period()
		if not self.status:
			self.status = STATUS_DRAFT

	def apply_fiscal_year(self):
		"""Fill the period from the selected fiscal year: one choice instead of two dates."""
		if self.period_type != PERIOD_FISCAL_YEAR or not self.fiscal_year:
			return

		year = frappe.get_cached_value(
			"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
		)
		if year:
			self.from_date = year.year_start_date
			self.to_date = year.year_end_date

	def validate_fiscal_year_company(self):
		"""A fiscal year restricted to other companies must not be used for this one."""
		if self.period_type != PERIOD_FISCAL_YEAR or not self.fiscal_year or not self.company:
			return

		companies = frappe.get_all(
			"Fiscal Year Company", filters={"parent": self.fiscal_year}, pluck="company"
		)
		if companies and self.company not in companies:
			frappe.throw(
				f"Das Geschäftsjahr {self.fiscal_year} gilt nicht für das Unternehmen {self.company}."
			)

	def validate_period(self):
		if not (self.from_date and self.to_date):
			return

		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(
				"Das Datum <b>Von</b> liegt nach dem Datum <b>Bis</b>. Bitte korrigieren Sie den Zeitraum."
			)

	# ------------------------------------------------------------------ actions

	@frappe.whitelist()
	def start_export(self) -> dict:
		"""Queue the background job that builds the package."""
		self.check_permission("write")

		if self.status in BUSY_STATES:
			frappe.throw("Dieser Export läuft bereits. Bitte warten Sie, bis er abgeschlossen ist.")

		if not frappe.db.exists("Company", self.company):
			frappe.throw(f"Das Unternehmen {self.company} existiert nicht.")

		self.db_set(
			{
				"status": STATUS_QUEUED,
				"error_message": None,
				"started_at": None,
				"finished_at": None,
			}
		)

		job_name = f"gdpdu-export-{self.name}"
		frappe.enqueue(
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export.run_export",
			queue="long",
			timeout=JOB_TIMEOUT,
			job_name=job_name,
			enqueue_after_commit=True,
			export_name=self.name,
		)
		return {"name": self.name, "company": self.company, "status": self.status, "job_name": job_name}

	@frappe.whitelist()
	def get_status(self) -> dict:
		"""Read-only snapshot: period, state, package, protocol summary and warnings.

		Named ``get_status`` because the document has a ``status`` field, which would
		shadow a method of the same name on the instance.
		"""
		self.check_permission("read")

		data = {fieldname: self.get(fieldname) for fieldname in EXPORT_FIELDS}
		data["is_busy"] = self.status in BUSY_STATES
		data["is_finished"] = self.status in FINISHED_STATES
		data["files"] = self.list_files()
		data["download_url"] = self.export_file or None
		data["protocol"] = self.protocol_summary()
		data["warnings"] = data["protocol"].get("warnings", [])
		return data

	@frappe.whitelist()
	def list_files(self) -> list[dict]:
		"""Files attached to this export (the ZIP package of the last successful run)."""
		self.check_permission("read")

		rows = frappe.get_all(
			"File",
			filters={"attached_to_doctype": self.doctype, "attached_to_name": self.name},
			fields=["name", "file_name", "file_url", "file_size", "is_private", "creation"],
			order_by="creation desc",
		)
		return [
			{
				"file": row.name,
				"file_name": row.file_name,
				"file_url": row.file_url,
				"file_size": row.file_size,
				"is_private": row.is_private,
				"created_at": row.creation,
				"is_package": row.file_url == self.export_file,
			}
			for row in rows
		]

	@frappe.whitelist()
	def verify_package(self) -> dict:
		"""Re-check the attached ZIP: declared files present, index.xml valid against the DTD."""
		self.check_permission("read")

		if not self.export_file:
			return {
				"ok": False,
				"checked": False,
				"message": "Es ist kein Export-Paket hinterlegt. Bitte erstellen Sie den Export zuerst.",
			}

		content = read_attachment_bytes(frappe.get_doc("File", {"file_url": self.export_file}))
		problems: list[str] = []

		try:
			with zipfile.ZipFile(io.BytesIO(content)) as archive:
				names = set(archive.namelist())
				index_xml = archive.read(INDEX_FILE_NAME).decode("utf-8") if INDEX_FILE_NAME in names else ""
				dtd_content = archive.read(DTD_FILE_NAME) if DTD_FILE_NAME in names else None
		except zipfile.BadZipFile:
			return {"ok": False, "checked": True, "message": "Die Datei ist kein lesbares ZIP-Archiv."}

		expected = [INDEX_FILE_NAME, PROTOCOL_FILE_NAME, README_FILE_NAME] + [
			table.filename for table in get_tables()
		]
		missing = [name for name in expected if name not in names]
		if missing:
			problems.append(f"Fehlende Dateien im Paket: {', '.join(missing)}")

		if DTD_FILE_NAME not in names:
			problems.append(f"Die Datei {DTD_FILE_NAME} fehlt im Paket.")

		validation = validate_index_xml(index_xml, dtd_content or get_dtd().content) if index_xml else None
		if validation and validation.performed and not validation.valid:
			problems.append("Die index.xml entspricht nicht der DTD: " + "; ".join(validation.errors[:3]))

		return {
			"ok": not problems,
			"checked": True,
			"file_name": self.package_name,
			"files_in_package": sorted(names),
			"missing_files": missing,
			"dtd_included": DTD_FILE_NAME in names,
			"validation_performed": bool(validation and validation.performed),
			"validation_valid": bool(validation and validation.valid),
			"validation_message": (
				validation.skipped_reason or "; ".join(validation.errors[:3]) if validation else ""
			),
			"problems": problems,
			"message": "Das Paket ist vollständig." if not problems else " ".join(problems),
		}

	# ------------------------------------------------------------------ helpers

	def protocol_summary(self) -> dict:
		"""The protocol of the last run as data (empty before the first run)."""
		if not self.protocol_json:
			return {}
		try:
			return json.loads(self.protocol_json)
		except ValueError:
			return {}


@frappe.whitelist()
def get_export_scope() -> list[dict]:
	"""Describe the exported tables for the form: one source of truth with the schema."""
	frappe.has_permission("GDPdU Export", "read", throw=True)
	return [
		{"filename": table.filename, "name": table.name, "hint": table.user_hint} for table in get_tables()
	]


def run_export(export_name: str) -> None:
	"""Background job: build the package and attach it to the document."""
	doc = frappe.get_doc("GDPdU Export", export_name)
	doc.db_set({"status": STATUS_RUNNING, "started_at": now_datetime()})
	frappe.db.commit()

	try:
		result = build_package(
			doc.company,
			doc.from_date,
			doc.to_date,
			progress=_progress_reporter(doc),
		)
		file_url = _attach_package(doc, result)
		protocol = result.protocol

		doc.db_set(
			{
				"status": STATUS_COMPLETED,
				"export_file": file_url,
				"package_name": result.file_name,
				"protocol_html": protocol.as_html(),
				"protocol_json": json.dumps(protocol.as_dict(), ensure_ascii=False),
				"journal_rows": protocol.journal_rows,
				"dtd_included": 1 if protocol.dtd_included else 0,
				"app_version": protocol.app_version,
				"finished_at": now_datetime(),
				"error_message": None,
			}
		)
		frappe.db.commit()

	except Exception as exception:
		frappe.db.rollback()
		frappe.log_error(
			title=f"GDPdU Export {export_name} fehlgeschlagen",
			message=frappe.get_traceback(with_context=True),
		)
		doc.db_set(
			{
				"status": STATUS_FAILED,
				"error_message": _failure_message(exception),
				"finished_at": now_datetime(),
			}
		)
		frappe.db.commit()

	finally:
		frappe.publish_realtime(
			REALTIME_EVENT,
			{"name": export_name, "status": frappe.db.get_value("GDPdU Export", export_name, "status")},
			doctype="GDPdU Export",
			docname=export_name,
			after_commit=True,
		)


def _progress_reporter(doc: Document):
	def report(percent: int, message: str) -> None:
		frappe.publish_progress(
			percent,
			title="GoBD-Export wird erstellt",
			doctype=doc.doctype,
			docname=doc.name,
			description=message,
		)

	return report


def _attach_package(doc: Document, result) -> str:
	"""Attach the ZIP as a private file, replacing the package of an earlier run."""
	_remove_previous_packages(doc)

	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": result.file_name,
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"attached_to_field": "export_file",
			"is_private": 1,
			"content": result.content,
		}
	).insert(ignore_permissions=True)

	return file_doc.file_url


def _remove_previous_packages(doc: Document) -> None:
	previous = frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"attached_to_field": "export_file",
		},
		pluck="name",
	)
	for name in previous:
		frappe.delete_doc("File", name, ignore_permissions=True, delete_permanently=True)


def _failure_message(exception: Exception) -> str:
	"""Turn an exception into something a non-technical user can act on."""
	if isinstance(exception, frappe.ValidationError) and str(exception):
		return frappe.utils.strip_html(str(exception))

	return (
		"Der Export konnte nicht erstellt werden. Bitte versuchen Sie es erneut. "
		"Falls der Fehler bleibt, findet Ihr Administrator die technischen Details "
		"unter Fehlerprotokoll (Error Log)."
	)
