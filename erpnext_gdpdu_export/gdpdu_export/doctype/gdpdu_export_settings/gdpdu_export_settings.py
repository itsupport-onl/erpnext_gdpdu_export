"""Controller of the GDPdU Export Settings single document."""

from __future__ import annotations

import frappe
from frappe.model.document import Document

from erpnext_gdpdu_export.gdpdu.dtd import read_attachment_bytes
from erpnext_gdpdu_export.gdpdu.index_xml import DTD_FILE_NAME


class GDPdUExportSettings(Document):
	def validate(self):
		self.validate_dtd_file()

	def validate_dtd_file(self):
		"""Reject an obviously wrong upload before it ends up on a data medium."""
		if not self.dtd_file:
			return

		before = self.get_doc_before_save()
		if before and before.get("dtd_file") == self.dtd_file:
			return

		content = self._read_dtd()
		if content is None:
			return

		if b"<!ELEMENT DataSet" not in content:
			frappe.throw(
				f"Die hochgeladene Datei sieht nicht wie die {DTD_FILE_NAME} aus. "
				"Bitte laden Sie die unveränderte Original-DTD des Beschreibungsstandards hoch."
			)

	def _read_dtd(self) -> bytes | None:
		try:
			return read_attachment_bytes(frappe.get_doc("File", {"file_url": self.dtd_file}))
		except Exception:
			return None
