"""Access to the Audicon DTD and validation of the generated index.xml.

``gdpdu-01-08-2002.dtd`` is a third-party artefact (© Audicon GmbH) and is never
modified by this app (CLAUDE.md rule 4). It is not shipped with this repository;
administrators upload it once in *GDPdU Export Settings* or drop it into
``erpnext_gdpdu_export/resources/``.

Only :func:`get_dtd` touches Frappe, and it imports it lazily, so the validation
helpers stay usable in plain unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .index_xml import DTD_FILE_NAME

BUNDLED_DTD_PATH = Path(__file__).resolve().parent.parent / "resources" / DTD_FILE_NAME

SOURCE_SETTINGS = "settings"
SOURCE_BUNDLED = "bundled"


@dataclass
class DtdResult:
	"""Where the DTD came from — ``content`` is ``None`` when it is unavailable."""

	content: bytes | None = None
	source: str | None = None


@dataclass
class ValidationResult:
	"""Outcome of validating index.xml against the DTD."""

	performed: bool = False
	valid: bool = False
	errors: list[str] = field(default_factory=list)
	#: Why validation could not run (missing DTD, missing lxml).
	skipped_reason: str = ""


def get_bundled_dtd() -> bytes | None:
	"""Return the DTD shipped inside the app, if an administrator placed it there."""
	if BUNDLED_DTD_PATH.is_file():
		return BUNDLED_DTD_PATH.read_bytes()
	return None


def get_dtd() -> DtdResult:
	"""Return the DTD from the settings attachment, else from ``resources/``."""
	content = _get_dtd_from_settings()
	if content:
		return DtdResult(content=content, source=SOURCE_SETTINGS)

	content = get_bundled_dtd()
	if content:
		return DtdResult(content=content, source=SOURCE_BUNDLED)

	return DtdResult()


def read_attachment_bytes(file_doc) -> bytes:
	"""Return the raw bytes of a File document without touching its content.

	The DTD must stay byte identical (CLAUDE.md rule 4), so the file is read in
	binary mode; ``get_content()`` is only the fallback for storage backends
	that do not keep the file on the local disk.
	"""
	path = file_doc.get_full_path()
	if path and Path(path).is_file():
		return Path(path).read_bytes()

	content = file_doc.get_content()
	return content if isinstance(content, bytes) else content.encode("utf-8")


def _get_dtd_from_settings() -> bytes | None:
	import frappe

	file_url = frappe.db.get_single_value("GDPdU Export Settings", "dtd_file")
	if not file_url:
		return None

	try:
		return read_attachment_bytes(frappe.get_doc("File", {"file_url": file_url}))
	except Exception:
		# A missing or unreadable attachment must never break an export; the
		# protocol reports the missing DTD instead.
		frappe.log_error(
			title="GDPdU Export: DTD-Anhang nicht lesbar",
			message=frappe.get_traceback(),
		)
		return None


def validate_index_xml(xml_text: str, dtd_content: bytes | None) -> ValidationResult:
	"""Validate ``xml_text`` against the DTD; never raises."""
	if not dtd_content:
		return ValidationResult(
			skipped_reason=f"Die Datei {DTD_FILE_NAME} liegt nicht vor.",
		)

	try:
		from io import BytesIO

		from lxml import etree
	except ImportError:
		return ValidationResult(skipped_reason="Die Bibliothek lxml ist nicht installiert.")

	try:
		dtd = etree.DTD(BytesIO(dtd_content))
	except Exception as exc:
		return ValidationResult(skipped_reason=f"Die DTD konnte nicht gelesen werden: {exc}")

	# no_network/load_dtd: never resolve the external DOCTYPE reference.
	parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
	try:
		root = etree.fromstring(xml_text.encode("utf-8"), parser=parser)
	except etree.XMLSyntaxError as exc:
		return ValidationResult(performed=True, valid=False, errors=[str(exc)])

	if dtd.validate(root):
		return ValidationResult(performed=True, valid=True)

	return ValidationResult(
		performed=True,
		valid=False,
		errors=[str(error) for error in dtd.error_log],
	)
