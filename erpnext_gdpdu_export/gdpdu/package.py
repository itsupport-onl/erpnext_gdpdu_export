"""Builds the export package: CSV files, index.xml, DTD and Prüfprotokoll as ZIP.

Orchestration only — the format rules live in :mod:`gdpdu.csv_writer` and
:mod:`gdpdu.index_xml`, the data comes from :mod:`gdpdu.extractors`. Nothing here
writes accounting data (CLAUDE.md rule 1).
"""

from __future__ import annotations

import re
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import frappe
from frappe.utils import getdate, now_datetime

from .. import __version__
from .csv_writer import write_csv_file
from .dtd import get_dtd, validate_index_xml
from .extractors import ExtractionContext, get_extractor
from .formats import format_date
from .index_xml import DTD_FILE_NAME, INDEX_FILE_NAME, build_index_xml
from .protocol import Protocol
from .schema import get_tables

PROTOCOL_FILE_NAME = "pruefprotokoll.txt"
README_FILE_NAME = "LIESMICH.txt"

ProgressCallback = Callable[[int, str], None]


@dataclass
class ExportResult:
	"""The finished package plus everything the user should see about it."""

	file_name: str
	content: bytes
	protocol: Protocol


def build_package(
	company: str,
	from_date,
	to_date,
	*,
	progress: ProgressCallback | None = None,
) -> ExportResult:
	"""Create the complete export package for one company and period."""
	from_date = getdate(from_date)
	to_date = getdate(to_date)
	if from_date > to_date:
		frappe.throw("Das Startdatum liegt nach dem Enddatum.")

	protocol = _new_protocol(company, from_date, to_date)
	ctx = ExtractionContext(
		company=company,
		from_date=str(from_date),
		to_date=str(to_date),
		currency=protocol.currency,
		protocol=protocol,
	)

	tables = get_tables()
	with tempfile.TemporaryDirectory(prefix="gdpdu-") as workdir:
		folder = Path(workdir)

		for index, table in enumerate(tables):
			_report(progress, 5 + int(index * 70 / len(tables)), f"Exportiere {table.name} …")
			rows = get_extractor(table.key)(ctx)
			count = write_csv_file(table, rows, folder / table.filename)
			protocol.add_table(table.filename, table.name, count, table.user_hint)

		_check_plausibility(protocol)

		_report(progress, 80, "Erstelle Beschreibungsdatei index.xml …")
		index_xml = build_index_xml(
			tables,
			supplier_name=protocol.company,
			supplier_location=protocol.supplier_location,
			comment=_supplier_comment(protocol),
			from_date=from_date,
			to_date=to_date,
		)
		(folder / INDEX_FILE_NAME).write_text(index_xml, encoding="utf-8", newline="")

		_report(progress, 85, "Prüfe die Beschreibungsdatei …")
		_add_dtd(folder, index_xml, protocol)

		protocol.package_name = _package_name(company, from_date, to_date)
		(folder / PROTOCOL_FILE_NAME).write_text(protocol.as_text(), encoding="utf-8", newline="")
		(folder / README_FILE_NAME).write_text(_readme_text(protocol), encoding="utf-8", newline="")

		_report(progress, 92, "Packe das Export-Paket …")
		content = _zip_folder(folder)

	_report(progress, 100, "Export fertiggestellt.")
	return ExportResult(file_name=protocol.package_name, content=content, protocol=protocol)


# ---------------------------------------------------------------------- setup


def _new_protocol(company: str, from_date, to_date) -> Protocol:
	company_doc = frappe.get_cached_doc("Company", company)
	protocol = Protocol(
		company=company_doc.company_name or company,
		from_date=from_date,
		to_date=to_date,
		currency=company_doc.default_currency or "",
		app_version=__version__,
		created_by=frappe.session.user,
		created_at=now_datetime(),
	)
	protocol.supplier_location = _company_location(company) or company_doc.country or ""

	if not protocol.currency:
		frappe.throw(f"Für das Unternehmen {company} ist keine Währung hinterlegt.")

	return protocol


def _company_location(company: str) -> str:
	"""City of the company address — ``<Location>`` of the data supplier."""
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


def _supplier_comment(protocol: Protocol) -> str:
	return (
		f"GoBD-Datentraegerueberlassung {format_date(protocol.from_date)}-"
		f"{format_date(protocol.to_date)}, erstellt mit erpnext_gdpdu_export {protocol.app_version}"
	)


def _package_name(company: str, from_date, to_date) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr") or company
	slug = re.sub(r"[^A-Za-z0-9]+", "-", abbr).strip("-") or "Export"
	return f"GoBD-Export_{slug}_{format_date(from_date)}_{format_date(to_date)}.zip"


# ------------------------------------------------------------------- checking


def _check_plausibility(protocol: Protocol) -> None:
	if not protocol.journal_rows:
		protocol.add_warning(
			code="no_bookings",
			message="Im gewählten Zeitraum wurden keine Buchungen gefunden.",
			hint=(
				"Prüfen Sie Unternehmen und Zeitraum. Ein Paket ohne Buchungen ist für eine "
				"Betriebsprüfung nicht verwertbar."
			),
		)

	if not protocol.is_balanced:
		protocol.add_warning(
			code="unbalanced",
			message=(
				"Die Summe der Soll-Beträge weicht von der Summe der Haben-Beträge ab "
				f"(Differenz: {protocol.difference} {protocol.currency})."
			),
			hint=(
				"Das deutet auf unvollständige Buchungen im Zeitraum hin. Klären Sie die "
				"Differenz vor der Übergabe an den Prüfer mit Ihrer Buchhaltung."
			),
		)


def _add_dtd(folder: Path, index_xml: str, protocol: Protocol) -> None:
	"""Place the DTD next to index.xml and validate against it."""
	result = get_dtd()
	if result.content:
		(folder / DTD_FILE_NAME).write_bytes(result.content)
		protocol.dtd_included = True
		protocol.dtd_source = result.source or ""
	else:
		protocol.add_warning(
			code="missing_dtd",
			message=f"Die Datei {DTD_FILE_NAME} fehlt im Export-Paket.",
			hint=(
				"Der Beschreibungsstandard verlangt diese Datei auf dem Datenträger. Laden Sie "
				"sie einmalig unter Einstellungen > GDPdU Export Settings hoch; alle künftigen "
				"Exporte enthalten sie dann automatisch."
			),
		)

	validation = validate_index_xml(index_xml, result.content)
	protocol.validation_performed = validation.performed
	protocol.validation_valid = validation.valid
	protocol.validation_message = validation.skipped_reason or "; ".join(validation.errors[:3])

	if validation.performed and not validation.valid:
		protocol.add_warning(
			code="invalid_index_xml",
			message="Die Beschreibungsdatei index.xml entspricht nicht der DTD.",
			hint=(
				"Bitte melden Sie diesen Fehler mit dem Prüfprotokoll als Issue, das Paket "
				"sollte so nicht übergeben werden."
			),
			sample=validation.errors[0] if validation.errors else "",
		)


# -------------------------------------------------------------------- writing


def _zip_folder(folder: Path) -> bytes:
	archive_path = folder.parent / f"{folder.name}.zip"
	with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
		for path in sorted(folder.iterdir()):
			if path.is_file():
				archive.write(path, arcname=path.name)

	content = archive_path.read_bytes()
	archive_path.unlink()
	return content


def _readme_text(protocol: Protocol) -> str:
	files = "\n".join(f"  {table.filename:<26} {table.hint or table.name}" for table in protocol.tables)
	return f"""GoBD-Datenträgerüberlassung (Z3-Zugriff, § 147 Abs. 6 AO)
========================================================

Unternehmen: {protocol.company}
Zeitraum:    {protocol.period_label}
Erstellt am: {protocol.created_at.strftime("%d.%m.%Y %H:%M") if protocol.created_at else ""}

Dieses Paket enthält die Finanzbuchhaltung des oben genannten Zeitraums im
Beschreibungsstandard für die Datenträgerüberlassung (Audicon, Version 1.6).
Es ist für den Import in die Prüfsoftware IDEA bestimmt.

Inhalt
------
  index.xml                  Maschinenlesbare Beschreibung aller Dateien
  {DTD_FILE_NAME}      Zugehörige DTD (Bestandteil des Standards)
{files}
  {PROTOCOL_FILE_NAME}          Prüfprotokoll dieses Exports
  {README_FILE_NAME}                Diese Datei

Format
------
  Zeichensatz:     UTF-8 (ohne BOM)
  Spaltentrenner:  ;
  Satztrenner:     CRLF
  Texteinschluss:  "  (im Text verdoppelt)
  Dezimaltrenner:  ,   (kein Tausendertrenner)
  Datum:           JJJJMMTT
  Beträge:         zwei Nachkommastellen, negatives Vorzeichen vorangestellt
  Kopfzeile:       vorhanden, in index.xml per Range From=2 übersprungen

Hinweise
--------
- index.xml und {DTD_FILE_NAME} müssen zusammen im selben
  Verzeichnis liegen, sonst kann IDEA das Paket nicht einlesen.
- Die Dateien wurden ausschließlich lesend aus dem ERP-System erzeugt;
  Buchungsdaten wurden dabei nicht verändert.
- Das Paket enthält personenbezogene Daten. Übergabe an den Prüfer nur
  auf einem verschlüsselten Datenträger bzw. Weg.

Erstellt mit erpnext_gdpdu_export {protocol.app_version} (Open Source, MIT).
"""


def _report(progress: ProgressCallback | None, percent: int, message: str) -> None:
	if progress:
		progress(percent, message)
