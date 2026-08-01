"""Controller of the GDPdU Export document.

The document only collects the user's choices and shows the result; the actual
package is built in a background job so large journals cannot run into a
request timeout.
"""

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from erpnext_gdpdu_export.gdpdu.package import build_package
from erpnext_gdpdu_export.gdpdu.schema import get_tables

STATUS_DRAFT = "Entwurf"
STATUS_QUEUED = "In Warteschlange"
STATUS_RUNNING = "Läuft"
STATUS_COMPLETED = "Fertig"
STATUS_FAILED = "Fehlgeschlagen"

BUSY_STATES = (STATUS_QUEUED, STATUS_RUNNING)

PERIOD_FISCAL_YEAR = "Geschäftsjahr"

#: Sent to the browser so the form can refresh itself when the job is done.
REALTIME_EVENT = "gdpdu_export_update"

JOB_TIMEOUT = 4 * 60 * 60


class GDPdUExport(Document):
	def validate(self):
		self.apply_fiscal_year()
		self.validate_period()
		if not self.status:
			self.status = STATUS_DRAFT

	def apply_fiscal_year(self):
		"""Fill the period from the selected fiscal year — one choice instead of two dates."""
		if self.period_type != PERIOD_FISCAL_YEAR or not self.fiscal_year:
			return

		year = frappe.get_cached_value(
			"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
		)
		if year:
			self.from_date = year.year_start_date
			self.to_date = year.year_end_date

	def validate_period(self):
		if not (self.from_date and self.to_date):
			return

		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(
				"Das Datum <b>Von</b> liegt nach dem Datum <b>Bis</b>. Bitte korrigieren Sie den Zeitraum."
			)

	@frappe.whitelist()
	def start_export(self) -> str:
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

		frappe.enqueue(
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export.run_export",
			queue="long",
			timeout=JOB_TIMEOUT,
			job_name=f"gdpdu-export-{self.name}",
			enqueue_after_commit=True,
			export_name=self.name,
		)
		return self.status


@frappe.whitelist()
def get_export_scope() -> list[dict]:
	"""Describe the exported tables for the form — one source of truth with the schema."""
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
