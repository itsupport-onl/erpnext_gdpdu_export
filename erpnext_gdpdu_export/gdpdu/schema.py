"""Declarative table definitions — the single source of truth of this app.

The CSV writer and the index.xml generator both consume these definitions, so a
column can never exist in one place and be missing in the other (CLAUDE.md rule 2).
Field mapping and column order follow SPEC.md; changes go into SPEC.md first.

No Frappe dependency, so this module is unit testable with a plain interpreter.
"""

from __future__ import annotations

from dataclasses import dataclass

from .formats import DATE_FORMAT, TIME_FORMAT

ALPHANUMERIC = "AlphaNumeric"
NUMERIC = "Numeric"
DATE = "Date"

COLUMN_TYPES = (ALPHANUMERIC, NUMERIC, DATE)

#: Decimals for all monetary columns (KONZEPT.md section 2).
DEFAULT_ACCURACY = 2


@dataclass(frozen=True)
class ValueMap:
	"""Explains an encoded value to the auditor: ``<Map><From>1</From><To>Ja</To></Map>``."""

	from_value: str
	to_value: str
	description: str = ""


@dataclass(frozen=True)
class Column:
	"""One CSV column and its index.xml declaration.

	``name`` is used as the CSV header *and* as ``<Name>`` in index.xml, and it is
	the key the extractors put into their row dicts.
	"""

	name: str
	type: str = ALPHANUMERIC
	description: str = ""
	is_key: bool = False
	accuracy: int | None = None
	max_length: int | None = None
	date_format: str = DATE_FORMAT
	maps: tuple[ValueMap, ...] = ()

	def __post_init__(self):
		if self.type not in COLUMN_TYPES:
			raise ValueError(f"Column {self.name}: unknown type {self.type!r}")
		if self.type != NUMERIC and self.accuracy is not None:
			raise ValueError(f"Column {self.name}: accuracy is only valid for {NUMERIC}")
		if self.type != ALPHANUMERIC and self.max_length is not None:
			raise ValueError(f"Column {self.name}: max_length is only valid for {ALPHANUMERIC}")


@dataclass(frozen=True)
class ForeignKey:
	"""``<ForeignKey>`` — ``references`` is the ``<Name>`` of the target table."""

	columns: tuple[str, ...]
	references: str


@dataclass(frozen=True)
class Table:
	"""One CSV file plus its complete index.xml declaration."""

	key: str
	filename: str
	name: str
	description: str
	columns: tuple[Column, ...]
	foreign_keys: tuple[ForeignKey, ...] = ()
	#: Shown to the user in the Desk so non-technical users know what they export.
	user_hint: str = ""

	def __post_init__(self):
		names = [column.name for column in self.columns]
		if len(names) != len(set(names)):
			raise ValueError(f"Table {self.key}: duplicate column names")
		if not self.key_columns:
			raise ValueError(f"Table {self.key}: at least one key column is required")

		# The DTD is (VariablePrimaryKey+, VariableColumn*): key columns are matched
		# positionally and must therefore be the leading columns of the file.
		key_flags = [column.is_key for column in self.columns]
		if key_flags != sorted(key_flags, reverse=True):
			raise ValueError(f"Table {self.key}: key columns must come first")

		for foreign_key in self.foreign_keys:
			for column_name in foreign_key.columns:
				if column_name not in names:
					raise ValueError(f"Table {self.key}: foreign key column {column_name} does not exist")

	@property
	def key_columns(self) -> tuple[Column, ...]:
		return tuple(column for column in self.columns if column.is_key)

	@property
	def data_columns(self) -> tuple[Column, ...]:
		return tuple(column for column in self.columns if not column.is_key)

	@property
	def header(self) -> tuple[str, ...]:
		return tuple(column.name for column in self.columns)


def _amount(name: str, description: str) -> Column:
	return Column(name=name, type=NUMERIC, accuracy=DEFAULT_ACCURACY, description=description)


JOURNAL = Table(
	key="journal",
	filename="journal.csv",
	name="Buchungsjournal",
	description=(
		"Vollstaendiges Buchungsjournal der Finanzbuchhaltung im Exportzeitraum "
		"(alle Sachkonten, Soll- und Habenbewegungen je Buchungszeile)."
	),
	user_hint="Alle Buchungen des Zeitraums (Journal) — die Haupttabelle der Prüfung.",
	columns=(
		Column(
			name="JournalID",
			is_key=True,
			description="Eindeutige Kennung der Buchungszeile (technischer Schluessel des Systems).",
		),
		Column(name="Buchungsdatum", type=DATE, description="Datum der Verbuchung."),
		Column(
			name="Belegdatum",
			type=DATE,
			description="Datum des zugrunde liegenden Belegs.",
		),
		Column(name="Belegart", description="Art des Belegs, z. B. Ausgangsrechnung oder Buchungssatz."),
		Column(name="Belegnummer", description="Nummer des Belegs im System."),
		Column(
			name="Konto",
			description="Sachkonto der Buchungszeile, siehe Tabelle Kontenplan.",
		),
		Column(name="Kontobezeichnung", description="Bezeichnung des Sachkontos (Redundanz zum Kontenplan)."),
		_amount("Soll", "Sollbetrag in Buchungswaehrung des Unternehmens."),
		_amount("Haben", "Habenbetrag in Buchungswaehrung des Unternehmens."),
		Column(name="Waehrung", max_length=3, description="Waehrung des Unternehmens (ISO-Code)."),
		Column(
			name="GegenparteiTyp",
			description="Art der Gegenpartei: Customer (Debitor), Supplier (Kreditor), Employee oder leer.",
		),
		Column(
			name="Gegenpartei",
			description=(
				"Kennung der Gegenpartei. Bei GegenparteiTyp=Customer siehe Tabelle Debitoren, "
				"bei GegenparteiTyp=Supplier siehe Tabelle Kreditoren."
			),
		),
		Column(
			name="Gegenkonto",
			description=(
				"Sammelangabe der Gegenseite aus dem System, mehrere Werte durch Komma getrennt. "
				"Enthaelt in der Regel die Gegenkonten, bei Buchungen auf Personenkonten "
				"stattdessen die Bezeichnung der Gegenpartei."
			),
		),
		Column(name="Buchungstext", description="Buchungstext bzw. Bemerkung zur Buchungszeile."),
		Column(name="Kostenstelle", description="Kostenstelle der Buchungszeile."),
		Column(name="ErfasstAm", type=DATE, description="Datum der Erfassung im System."),
		Column(
			name="ErfasstUm",
			description="Uhrzeit der Erfassung im System.",
			maps=(ValueMap(from_value=TIME_FORMAT, to_value=TIME_FORMAT, description="Zeitformat"),),
		),
		Column(name="ErfasstVon", description="Benutzerkennung des Erfassers."),
	),
	foreign_keys=(ForeignKey(columns=("Konto",), references="Kontenplan"),),
)

ACCOUNTS = Table(
	key="accounts",
	filename="kontenplan.csv",
	name="Kontenplan",
	description="Vollstaendiger Kontenplan (Sachkonten) des Unternehmens.",
	user_hint="Alle Sachkonten des Unternehmens mit Nummer, Bezeichnung und Typ.",
	columns=(
		Column(name="Konto", is_key=True, description="Kontonummer, ersatzweise Kontobezeichnung."),
		Column(name="Kontobezeichnung", description="Bezeichnung des Kontos."),
		Column(name="Kontotyp", description="Kontoart des Systems, z. B. Bank, Steuern, Forderungen."),
		Column(
			name="Wurzeltyp",
			description="Bilanz-/GuV-Zuordnung: Asset, Liability, Equity, Income oder Expense.",
			maps=(
				ValueMap(from_value="Asset", to_value="Aktiva"),
				ValueMap(from_value="Liability", to_value="Passiva"),
				ValueMap(from_value="Equity", to_value="Eigenkapital"),
				ValueMap(from_value="Income", to_value="Ertrag"),
				ValueMap(from_value="Expense", to_value="Aufwand"),
			),
		),
		Column(
			name="IstGruppe",
			description="Kennzeichen, ob es sich um ein Gruppen-/Sammelkonto ohne eigene Buchungen handelt.",
			maps=(
				ValueMap(from_value="0", to_value="Nein"),
				ValueMap(from_value="1", to_value="Ja"),
			),
		),
		Column(name="Waehrung", max_length=3, description="Kontowaehrung (ISO-Code)."),
	),
)


def _party_table(key: str, filename: str, name: str, description: str, user_hint: str) -> Table:
	return Table(
		key=key,
		filename=filename,
		name=name,
		description=description,
		user_hint=user_hint,
		columns=(
			Column(name="Kennung", is_key=True, description="Eindeutige Kennung im System."),
			Column(name="Name", description="Name bzw. Firmierung."),
			Column(name="Strasse", description="Strasse und Hausnummer der Hauptanschrift."),
			Column(name="PLZ", description="Postleitzahl der Hauptanschrift."),
			Column(name="Ort", description="Ort der Hauptanschrift."),
			Column(name="Land", description="Land der Hauptanschrift."),
			Column(name="UStIdNr", description="Umsatzsteuer-Identifikationsnummer bzw. Steuernummer."),
		),
	)


CUSTOMERS = _party_table(
	key="customers",
	filename="debitoren.csv",
	name="Debitoren",
	description="Debitorenstammdaten der im Zeitraum bebuchten Kunden.",
	user_hint="Kunden mit Buchungen im Zeitraum (Name, Anschrift, USt-IdNr.).",
)

SUPPLIERS = _party_table(
	key="suppliers",
	filename="kreditoren.csv",
	name="Kreditoren",
	description="Kreditorenstammdaten der im Zeitraum bebuchten Lieferanten.",
	user_hint="Lieferanten mit Buchungen im Zeitraum (Name, Anschrift, USt-IdNr.).",
)

TAXES = Table(
	key="taxes",
	filename="steuerkennzeichen.csv",
	name="Steuerkennzeichen",
	description="Steuerkonten des Unternehmens mit hinterlegtem Steuersatz und Verwendungsrichtung.",
	user_hint="Steuerkonten mit Steuersatz (Umsatzsteuer, Vorsteuer).",
	columns=(
		Column(name="Steuerkonto", is_key=True, description="Konto, auf dem die Steuer gebucht wird."),
		Column(name="Bezeichnung", description="Bezeichnung des Steuerkontos."),
		Column(
			name="Satz",
			type=NUMERIC,
			accuracy=DEFAULT_ACCURACY,
			description="Steuersatz in Prozent.",
		),
		Column(
			name="Richtung",
			description="Verwendung des Steuerkontos.",
			maps=(
				ValueMap(from_value="Sales", to_value="Ausgangsseite (Umsatzsteuer)"),
				ValueMap(from_value="Purchase", to_value="Eingangsseite (Vorsteuer)"),
				ValueMap(from_value="Sales+Purchase", to_value="Ausgangs- und Eingangsseite"),
			),
		),
	),
	foreign_keys=(ForeignKey(columns=("Steuerkonto",), references="Kontenplan"),),
)

#: Tables of the MVP, in export order. The journal runs first because it collects
#: which accounts and parties are actually used.
MVP_TABLES: tuple[Table, ...] = (JOURNAL, ACCOUNTS, CUSTOMERS, SUPPLIERS, TAXES)

ALL_TABLES: tuple[Table, ...] = MVP_TABLES


def get_tables() -> tuple[Table, ...]:
	"""Return the tables of an export package, in file order."""
	return MVP_TABLES


def get_table(key: str) -> Table:
	for table in ALL_TABLES:
		if table.key == key:
			return table
	raise KeyError(f"Unknown table {key!r}")


def validate_schema(tables: tuple[Table, ...] = ALL_TABLES) -> list[str]:
	"""Return a list of schema problems; an empty list means the schema is consistent."""
	problems: list[str] = []
	table_names = {table.name for table in tables}
	seen_files: set[str] = set()

	for table in tables:
		if table.filename in seen_files:
			problems.append(f"{table.key}: duplicate file name {table.filename}")
		seen_files.add(table.filename)

		if not table.description:
			problems.append(f"{table.key}: description is required for the auditor")

		for column in table.columns:
			if column.type == NUMERIC and column.accuracy is None:
				problems.append(f"{table.key}.{column.name}: numeric column without accuracy")
			if not column.description:
				problems.append(f"{table.key}.{column.name}: description is required for the auditor")

		for foreign_key in table.foreign_keys:
			if foreign_key.references not in table_names:
				problems.append(f"{table.key}: foreign key points to unknown table {foreign_key.references}")

	return problems


#: Columns whose sum must match across the whole export (GoBD plausibility check).
BALANCE_COLUMNS = ("Soll", "Haben")
