"""Prüfprotokoll — what the export contains and what the user has to check.

The protocol is the main feedback channel for non-technical users, so all texts
are German, free of jargon and each warning carries a concrete instruction.

No Frappe dependency, so this module is unit testable with a plain interpreter.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from decimal import Decimal

from .formats import format_date

MAX_WARNING_SAMPLES = 5


def format_amount_de(value) -> str:
	"""Return an amount in German notation: 1.234.567,89."""
	number = Decimal(str(value or 0)).quantize(Decimal("0.01"))
	formatted = f"{number:,.2f}"
	return formatted.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def format_date_de(value) -> str:
	"""Return a date as DD.MM.YYYY for on-screen texts."""
	iso = format_date(value)
	if not iso:
		return ""
	return f"{iso[6:8]}.{iso[4:6]}.{iso[0:4]}"


def escape_html(text) -> str:
	return (
		str(text if text is not None else "")
		.replace("&", "&amp;")
		.replace("<", "&lt;")
		.replace(">", "&gt;")
		.replace('"', "&quot;")
	)


@dataclass
class TableReport:
	"""One exported file as it appears in the protocol."""

	filename: str
	name: str
	rows: int
	hint: str = ""


@dataclass
class Warning:
	"""A finding the user should look at, aggregated per code."""

	code: str
	message: str
	hint: str = ""
	count: int = 1
	samples: list[str] = field(default_factory=list)


@dataclass
class Protocol:
	"""Collects everything worth reporting about one export run."""

	company: str = ""
	#: City of the company address — ``<Location>`` of the data supplier.
	supplier_location: str = ""
	from_date: datetime.date | str = ""
	to_date: datetime.date | str = ""
	currency: str = ""
	app_version: str = ""
	created_by: str = ""
	created_at: datetime.datetime | None = None
	package_name: str = ""

	tables: list[TableReport] = field(default_factory=list)
	warnings: list[Warning] = field(default_factory=list)

	total_debit: Decimal = Decimal("0.00")
	total_credit: Decimal = Decimal("0.00")

	dtd_included: bool = False
	dtd_source: str = ""
	validation_performed: bool = False
	validation_valid: bool = False
	validation_message: str = ""

	def add_table(self, filename: str, name: str, rows: int, hint: str = "") -> None:
		self.tables.append(TableReport(filename=filename, name=name, rows=rows, hint=hint))

	def add_warning(self, code: str, message: str, hint: str = "", sample: str = "") -> None:
		"""Add a warning; repeated codes are counted instead of repeated."""
		for warning in self.warnings:
			if warning.code == code:
				warning.count += 1
				if sample and len(warning.samples) < MAX_WARNING_SAMPLES:
					warning.samples.append(sample)
				return

		self.warnings.append(
			Warning(
				code=code,
				message=message,
				hint=hint,
				samples=[sample] if sample else [],
			)
		)

	def add_amounts(self, debit, credit) -> None:
		self.total_debit += Decimal(str(debit or 0))
		self.total_credit += Decimal(str(credit or 0))

	@property
	def difference(self) -> Decimal:
		return (self.total_debit - self.total_credit).quantize(Decimal("0.01"))

	@property
	def is_balanced(self) -> bool:
		return self.difference == Decimal("0.00")

	@property
	def total_rows(self) -> int:
		return sum(table.rows for table in self.tables)

	@property
	def journal_rows(self) -> int:
		for table in self.tables:
			if table.filename == "journal.csv":
				return table.rows
		return 0

	@property
	def period_label(self) -> str:
		return f"{format_date_de(self.from_date)} bis {format_date_de(self.to_date)}"

	# ------------------------------------------------------------------ output

	def as_text(self) -> str:
		"""Plain text protocol that travels inside the export package."""
		lines = [
			"Prüfprotokoll zur GoBD-Datenträgerüberlassung",
			"=" * 48,
			"",
			f"Unternehmen:      {self.company}",
			f"Zeitraum:         {self.period_label}",
			f"Währung:          {self.currency}",
			f"Erstellt am:      {self._created_at_label()}",
			f"Erstellt von:     {self.created_by}",
			f"Erstellt mit:     erpnext_gdpdu_export {self.app_version}",
			"",
			"Enthaltene Dateien",
			"-" * 48,
		]
		for table in self.tables:
			count = f"{table.rows:,}".replace(",", ".")
			unit = "Datensatz" if table.rows == 1 else "Datensätze"
			lines.append(f"{table.filename:<26} {count:>10} {unit}")

		lines += [
			"",
			"Summen des Buchungsjournals",
			"-" * 48,
			f"Summe Soll:       {format_amount_de(self.total_debit)} {self.currency}",
			f"Summe Haben:      {format_amount_de(self.total_credit)} {self.currency}",
			f"Differenz:        {format_amount_de(self.difference)} {self.currency}",
			(
				"Soll und Haben stimmen überein."
				if self.is_balanced
				else "ACHTUNG: Soll und Haben stimmen NICHT überein."
			),
			"",
			"Hinweise",
			"-" * 48,
		]

		if self.warnings:
			for warning in self.warnings:
				count = f" (betrifft {warning.count} Fälle)" if warning.count > 1 else ""
				lines.append(f"- {warning.message}{count}")
				if warning.samples:
					lines.append(f"  Beispiele: {', '.join(warning.samples)}")
				if warning.hint:
					lines.append(f"  Was tun: {warning.hint}")
		else:
			lines.append("- Keine Auffälligkeiten.")

		lines += ["", self._validation_label(), ""]
		return "\n".join(lines)

	def as_html(self) -> str:
		"""Rich protocol for the Desk form."""
		parts = [
			'<div class="gdpdu-protocol">',
			self._html_summary(),
			self._html_files(),
			self._html_balance(),
			self._html_warnings(),
			self._html_footer(),
			"</div>",
		]
		return "\n".join(parts)

	# ------------------------------------------------------------ html blocks

	def _html_summary(self) -> str:
		rows = [
			("Unternehmen", self.company),
			("Zeitraum", self.period_label),
			("Währung", self.currency),
			("Erstellt am", self._created_at_label()),
			("Erstellt von", self.created_by),
		]
		cells = "".join(
			'<div style="margin-bottom:4px">'
			f'<span style="color:var(--text-muted)">{escape_html(label)}:</span> '
			f"<b>{escape_html(value)}</b></div>"
			for label, value in rows
			if value
		)
		return f'<div style="margin-bottom:12px">{cells}</div>'

	def _html_files(self) -> str:
		rows = "".join(
			f"<tr><td>{escape_html(table.filename)}</td>"
			f"<td>{escape_html(table.name)}</td>"
			f'<td style="text-align:right">{table.rows:,}</td></tr>'.replace(",", ".")
			for table in self.tables
		)
		return (
			"<h5>Enthaltene Dateien</h5>"
			'<table class="table table-bordered" style="font-size:12px">'
			"<thead><tr><th>Datei</th><th>Inhalt</th>"
			'<th style="text-align:right">Datensätze</th></tr></thead>'
			f"<tbody>{rows}</tbody></table>"
		)

	def _html_balance(self) -> str:
		if self.is_balanced:
			indicator = '<span class="indicator-pill green">Soll und Haben stimmen überein</span>'
		else:
			indicator = '<span class="indicator-pill red">Soll und Haben weichen ab — bitte prüfen</span>'

		return (
			"<h5>Summen des Buchungsjournals</h5>"
			'<table class="table table-bordered" style="font-size:12px">'
			"<tbody>"
			f'<tr><td>Summe Soll</td><td style="text-align:right">'
			f"{format_amount_de(self.total_debit)} {escape_html(self.currency)}</td></tr>"
			f'<tr><td>Summe Haben</td><td style="text-align:right">'
			f"{format_amount_de(self.total_credit)} {escape_html(self.currency)}</td></tr>"
			f'<tr><td>Differenz</td><td style="text-align:right">'
			f"{format_amount_de(self.difference)} {escape_html(self.currency)}</td></tr>"
			f'</tbody></table><div style="margin-bottom:12px">{indicator}</div>'
		)

	def _html_warnings(self) -> str:
		if not self.warnings:
			return '<h5>Hinweise</h5><div class="indicator-pill green">Keine Auffälligkeiten gefunden</div>'

		items = []
		for warning in self.warnings:
			text = escape_html(warning.message)
			if warning.count > 1:
				text += f" <b>({warning.count}×)</b>"
			if warning.samples:
				text += (
					'<div style="color:var(--text-muted)">Beispiele: '
					f"{escape_html(', '.join(warning.samples))}</div>"
				)
			if warning.hint:
				text += f'<div style="color:var(--text-muted)">Was tun: {escape_html(warning.hint)}</div>'
			items.append(f'<li style="margin-bottom:8px">{text}</li>')

		return f'<h5>Hinweise</h5><ul style="padding-left:18px">{"".join(items)}</ul>'

	def _html_footer(self) -> str:
		return (
			f'<div style="color:var(--text-muted);font-size:11px;margin-top:12px">'
			f"{escape_html(self._validation_label())}<br>"
			f"Erstellt mit erpnext_gdpdu_export {escape_html(self.app_version)}"
			"</div>"
		)

	# ---------------------------------------------------------------- helpers

	def _created_at_label(self) -> str:
		if not self.created_at:
			return ""
		return self.created_at.strftime("%d.%m.%Y %H:%M")

	def _validation_label(self) -> str:
		if self.validation_performed and self.validation_valid:
			return "Die Beschreibungsdatei index.xml wurde erfolgreich gegen die DTD geprüft."
		if self.validation_performed:
			return f"Die Prüfung der index.xml hat Fehler ergeben: {self.validation_message}"
		return f"Die index.xml wurde nicht gegen die DTD geprüft ({self.validation_message})."
