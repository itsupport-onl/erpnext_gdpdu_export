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

# --------------------------------------------------------------- stage 2
#
# Document level, payments and open items. Not optional: the GoBD expect the
# records of the accounting system including the documents behind the postings
# (SPEC.md, stage 2). Tables without data are written as a header-only file.

MAP_YES_NO = (
	ValueMap(from_value="0", to_value="Nein"),
	ValueMap(from_value="1", to_value="Ja"),
)

_AUDIT_COLUMNS = (
	Column(name="ErfasstAm", type=DATE, description="Datum der Erfassung im System."),
	Column(
		name="ErfasstUm",
		description="Uhrzeit der Erfassung im System.",
		maps=(ValueMap(from_value=TIME_FORMAT, to_value=TIME_FORMAT, description="Zeitformat"),),
	),
	Column(name="ErfasstVon", description="Benutzerkennung des Erfassers."),
)


def _invoice_columns(party_columns: tuple[Column, ...]) -> tuple[Column, ...]:
	"""Columns shared by the outgoing and incoming invoice tables."""
	return (
		Column(name="Belegnummer", is_key=True, description="Belegnummer im System."),
		Column(name="Belegdatum", type=DATE, description="Datum des Belegs."),
		Column(name="Faelligkeit", type=DATE, description="Faelligkeitsdatum."),
		*party_columns,
		Column(name="Waehrung", max_length=3, description="Waehrung des Belegs (ISO-Code)."),
		Column(
			name="Wechselkurs",
			type=NUMERIC,
			accuracy=6,
			description="Umrechnungskurs in die Waehrung des Unternehmens.",
		),
		_amount("Netto", "Nettobetrag in Belegwaehrung."),
		_amount("Steuer", "Steuerbetrag in Belegwaehrung."),
		_amount("Brutto", "Bruttobetrag in Belegwaehrung."),
		_amount("NettoFirmenwaehrung", "Nettobetrag in der Waehrung des Unternehmens."),
		_amount("SteuerFirmenwaehrung", "Steuerbetrag in der Waehrung des Unternehmens."),
		_amount("BruttoFirmenwaehrung", "Bruttobetrag in der Waehrung des Unternehmens."),
		Column(
			name="IstGutschrift",
			description="Kennzeichen, ob der Beleg eine Gutschrift bzw. Stornorechnung ist.",
			maps=MAP_YES_NO,
		),
		Column(name="Status", description="Status des Belegs im System."),
		Column(name="Buchungstext", description="Bemerkung zum Beleg."),
		*_AUDIT_COLUMNS,
	)


def _invoice_item_columns(account_column: Column) -> tuple[Column, ...]:
	"""Columns shared by the position tables of both invoice types."""
	return (
		Column(name="PositionsID", is_key=True, description="Eindeutige Kennung der Belegposition."),
		Column(name="Belegnummer", description="Beleg, zu dem die Position gehoert."),
		Column(name="Position", type=NUMERIC, accuracy=0, description="Positionsnummer im Beleg."),
		Column(name="Artikel", description="Artikelnummer."),
		Column(name="Bezeichnung", description="Artikelbezeichnung."),
		Column(name="Menge", type=NUMERIC, accuracy=3, description="Menge."),
		Column(name="Einheit", description="Mengeneinheit."),
		_amount("Einzelpreis", "Einzelpreis in Belegwaehrung."),
		_amount("Netto", "Nettobetrag der Position in Belegwaehrung."),
		_amount("NettoFirmenwaehrung", "Nettobetrag der Position in der Waehrung des Unternehmens."),
		account_column,
		Column(name="Kostenstelle", description="Kostenstelle der Position."),
		Column(name="Steuervorlage", description="Steuervorlage der Position."),
	)


SALES_INVOICES = Table(
	key="sales_invoices",
	filename="ausgangsrechnungen.csv",
	name="Ausgangsrechnungen",
	description="Gebuchte Ausgangsrechnungen und Gutschriften des Exportzeitraums.",
	user_hint="Ausgangsrechnungen des Zeitraums (Kopfdaten inkl. Steuer und Faelligkeit).",
	columns=_invoice_columns(
		(
			Column(name="Debitor", description="Kennung des Kunden, siehe Tabelle Debitoren."),
			Column(name="DebitorName", description="Name des Kunden."),
		)
	),
	foreign_keys=(ForeignKey(columns=("Debitor",), references="Debitoren"),),
)

SALES_INVOICE_ITEMS = Table(
	key="sales_invoice_items",
	filename="ausgangsrechnungen_positionen.csv",
	name="Ausgangsrechnungspositionen",
	description="Einzelpositionen der exportierten Ausgangsrechnungen.",
	user_hint="Einzelpositionen der Ausgangsrechnungen (Artikel, Menge, Preis, Ertragskonto).",
	columns=_invoice_item_columns(
		Column(name="Ertragskonto", description="Ertragskonto der Position, siehe Tabelle Kontenplan.")
	),
	foreign_keys=(
		ForeignKey(columns=("Belegnummer",), references="Ausgangsrechnungen"),
		ForeignKey(columns=("Ertragskonto",), references="Kontenplan"),
	),
)

PURCHASE_INVOICES = Table(
	key="purchase_invoices",
	filename="eingangsrechnungen.csv",
	name="Eingangsrechnungen",
	description="Gebuchte Eingangsrechnungen und Gutschriften des Exportzeitraums.",
	user_hint="Eingangsrechnungen des Zeitraums (Kopfdaten inkl. Lieferantenbelegnummer).",
	columns=_invoice_columns(
		(
			Column(name="Kreditor", description="Kennung des Lieferanten, siehe Tabelle Kreditoren."),
			Column(name="KreditorName", description="Name des Lieferanten."),
			Column(
				name="LieferantenBelegnummer",
				description="Rechnungsnummer des Lieferanten.",
			),
			Column(
				name="LieferantenBelegdatum",
				type=DATE,
				description="Rechnungsdatum des Lieferanten.",
			),
		)
	),
	foreign_keys=(ForeignKey(columns=("Kreditor",), references="Kreditoren"),),
)

PURCHASE_INVOICE_ITEMS = Table(
	key="purchase_invoice_items",
	filename="eingangsrechnungen_positionen.csv",
	name="Eingangsrechnungspositionen",
	description="Einzelpositionen der exportierten Eingangsrechnungen.",
	user_hint="Einzelpositionen der Eingangsrechnungen (Artikel, Menge, Preis, Aufwandskonto).",
	columns=_invoice_item_columns(
		Column(name="Aufwandskonto", description="Aufwandskonto der Position, siehe Tabelle Kontenplan.")
	),
	foreign_keys=(
		ForeignKey(columns=("Belegnummer",), references="Eingangsrechnungen"),
		ForeignKey(columns=("Aufwandskonto",), references="Kontenplan"),
	),
)

PAYMENTS = Table(
	key="payments",
	filename="zahlungen.csv",
	name="Zahlungen",
	description="Gebuchte Zahlungsvorgaenge des Exportzeitraums.",
	user_hint="Zahlungen des Zeitraums (Ein- und Ausgang, Bankkonto, Betrag).",
	columns=(
		Column(name="Zahlungsnummer", is_key=True, description="Nummer des Zahlungsbelegs."),
		Column(name="Buchungsdatum", type=DATE, description="Datum der Verbuchung."),
		Column(
			name="Zahlungsart",
			description="Richtung des Zahlungsvorgangs.",
			maps=(
				ValueMap(from_value="Receive", to_value="Zahlungseingang"),
				ValueMap(from_value="Pay", to_value="Zahlungsausgang"),
				ValueMap(from_value="Internal Transfer", to_value="Umbuchung"),
			),
		),
		Column(
			name="GegenparteiTyp",
			description="Art der Gegenpartei: Customer (Debitor), Supplier (Kreditor) oder leer.",
		),
		Column(
			name="Gegenpartei",
			description=(
				"Kennung der Gegenpartei. Bei GegenparteiTyp=Customer siehe Tabelle Debitoren, "
				"bei GegenparteiTyp=Supplier siehe Tabelle Kreditoren."
			),
		),
		Column(name="KontoVon", description="Belastetes Konto, siehe Tabelle Kontenplan."),
		Column(name="KontoNach", description="Empfangendes Konto, siehe Tabelle Kontenplan."),
		_amount("Betrag", "Zahlbetrag in Belegwaehrung."),
		Column(name="Waehrung", max_length=3, description="Waehrung der Zahlung (ISO-Code)."),
		_amount("BetragFirmenwaehrung", "Zahlbetrag in der Waehrung des Unternehmens."),
		Column(name="Referenz", description="Beleg- oder Transaktionsnummer, z. B. der Bank."),
		Column(name="Referenzdatum", type=DATE, description="Datum der Referenz."),
		Column(name="Buchungstext", description="Bemerkung zum Zahlungsvorgang."),
		*_AUDIT_COLUMNS,
	),
	foreign_keys=(
		ForeignKey(columns=("KontoVon",), references="Kontenplan"),
		ForeignKey(columns=("KontoNach",), references="Kontenplan"),
	),
)

PAYMENT_ALLOCATIONS = Table(
	key="payment_allocations",
	filename="zahlungszuordnungen.csv",
	name="Zahlungszuordnungen",
	description="Zuordnung der Zahlungen zu den ausgeglichenen Belegen.",
	user_hint="Welche Zahlung welche Rechnung ausgleicht.",
	columns=(
		Column(name="ZuordnungsID", is_key=True, description="Eindeutige Kennung der Zuordnung."),
		Column(name="Zahlungsnummer", description="Zahlung, zu der die Zuordnung gehoert."),
		Column(name="Belegart", description="Art des ausgeglichenen Belegs."),
		Column(
			name="Belegnummer",
			description=(
				"Nummer des ausgeglichenen Belegs; je nach Belegart in der Tabelle "
				"Ausgangsrechnungen oder Eingangsrechnungen zu finden."
			),
		),
		_amount("ZugeordneterBetrag", "Auf den Beleg angerechneter Betrag."),
	),
	foreign_keys=(ForeignKey(columns=("Zahlungsnummer",), references="Zahlungen"),),
)


def _open_item_columns(party_description: str) -> tuple[Column, ...]:
	return (
		Column(name="Partei", is_key=True, description=party_description),
		Column(
			name="Beleg",
			is_key=True,
			description="Ursprungsbeleg des offenen Postens.",
		),
		Column(name="Konto", is_key=True, description="Personenkonto, siehe Tabelle Kontenplan."),
		Column(name="Belegart", description="Art des Ursprungsbelegs."),
		Column(name="Belegdatum", type=DATE, description="Datum des Ursprungsbelegs."),
		_amount("OffenerBetrag", "Zum Stichtag offener Betrag; positiv bedeutet offen."),
		Column(name="Waehrung", max_length=3, description="Waehrung des Unternehmens (ISO-Code)."),
		Column(name="Stichtag", type=DATE, description="Stichtag der Ermittlung (Ende des Exportzeitraums)."),
	)


OPEN_ITEMS_CUSTOMERS = Table(
	key="open_items_customers",
	filename="opos_debitoren.csv",
	name="OffenePostenDebitoren",
	description=(
		"Offene Posten der Debitoren zum Stichtag, ermittelt aus dem Buchungsjournal "
		"bis einschliesslich Ende des Exportzeitraums."
	),
	user_hint="Offene Forderungen zum Ende des Zeitraums.",
	columns=_open_item_columns("Kennung des Kunden, siehe Tabelle Debitoren."),
	foreign_keys=(
		ForeignKey(columns=("Partei",), references="Debitoren"),
		ForeignKey(columns=("Konto",), references="Kontenplan"),
	),
)

OPEN_ITEMS_SUPPLIERS = Table(
	key="open_items_suppliers",
	filename="opos_kreditoren.csv",
	name="OffenePostenKreditoren",
	description=(
		"Offene Posten der Kreditoren zum Stichtag, ermittelt aus dem Buchungsjournal "
		"bis einschliesslich Ende des Exportzeitraums."
	),
	user_hint="Offene Verbindlichkeiten zum Ende des Zeitraums.",
	columns=_open_item_columns("Kennung des Lieferanten, siehe Tabelle Kreditoren."),
	foreign_keys=(
		ForeignKey(columns=("Partei",), references="Kreditoren"),
		ForeignKey(columns=("Konto",), references="Kontenplan"),
	),
)

# --------------------------------------------------------------- stage 3
#
# Anlagenbuchhaltung — named explicitly by the GoBD (Rz. 159) next to the
# financial accounting, therefore part of every export as well.

ASSETS = Table(
	key="assets",
	filename="anlagegueter.csv",
	name="Anlagegueter",
	description=(
		"Anlagenverzeichnis zum Stichtag mit Anschaffungskosten, Abschreibungsparametern, "
		"kumulierter Abschreibung und Buchwert."
	),
	user_hint="Anlagevermögen mit Anschaffungskosten, Abschreibung und Buchwert.",
	columns=(
		Column(name="Anlagennummer", is_key=True, description="Nummer der Anlage im System."),
		Column(name="Bezeichnung", description="Bezeichnung der Anlage."),
		Column(name="Anlagenklasse", description="Anlagenkategorie."),
		Column(name="Artikel", description="Zugrunde liegende Artikelnummer."),
		Column(name="Anschaffungsdatum", type=DATE, description="Datum der Anschaffung."),
		Column(name="Inbetriebnahme", type=DATE, description="Beginn der Nutzung."),
		_amount("Anschaffungskosten", "Anschaffungskosten der Anlage."),
		_amount(
			"AnschaffungskostenGesamt",
			"Anschaffungskosten einschliesslich nachtraeglicher Anschaffungskosten.",
		),
		Column(name="Menge", type=NUMERIC, accuracy=3, description="Anzahl der Einheiten."),
		Column(name="Abschreibungsmethode", description="Methode der planmaessigen Abschreibung."),
		Column(
			name="AnzahlAbschreibungen",
			type=NUMERIC,
			accuracy=0,
			description="Geplante Anzahl der Abschreibungsbuchungen.",
		),
		Column(
			name="IntervallMonate",
			type=NUMERIC,
			accuracy=0,
			description="Abstand der Abschreibungsbuchungen in Monaten; 12 bedeutet jaehrlich.",
		),
		Column(name="Abschreibungsbeginn", type=DATE, description="Beginn der Abschreibung."),
		_amount("Restwert", "Erwarteter Restwert nach Ablauf der Nutzungsdauer."),
		_amount("AbschreibungEroeffnung", "Uebernommene kumulierte Abschreibung aus einem Altsystem."),
		_amount(
			"KumulierteAbschreibung",
			"Kumulierte Abschreibung bis zum Stichtag, nur gebuchte Betraege.",
		),
		_amount("BuchwertStichtag", "Buchwert zum Stichtag."),
		Column(name="Status", description="Status der Anlage im System."),
		Column(name="Abgangsdatum", type=DATE, description="Datum des Abgangs, falls vorhanden."),
		Column(name="Kostenstelle", description="Kostenstelle der Anlage."),
		Column(name="Standort", description="Standort der Anlage."),
		Column(name="Anlagenkonto", description="Bilanzkonto der Anlage, siehe Tabelle Kontenplan."),
		Column(name="AfAKonto", description="Aufwandskonto der Abschreibung, siehe Tabelle Kontenplan."),
		Column(
			name="KumAfAKonto",
			description="Konto der kumulierten Abschreibung, siehe Tabelle Kontenplan.",
		),
		Column(name="Stichtag", type=DATE, description="Stichtag der Werte (Ende des Exportzeitraums)."),
		*_AUDIT_COLUMNS,
	),
	foreign_keys=(
		ForeignKey(columns=("Anlagenkonto",), references="Kontenplan"),
		ForeignKey(columns=("AfAKonto",), references="Kontenplan"),
		ForeignKey(columns=("KumAfAKonto",), references="Kontenplan"),
	),
)

DEPRECIATIONS = Table(
	key="depreciations",
	filename="abschreibungen.csv",
	name="Abschreibungen",
	description="Abschreibungszeilen des Exportzeitraums je Anlage, geplant und gebucht.",
	user_hint="Abschreibungen des Zeitraums je Anlage.",
	columns=(
		Column(name="AbschreibungsID", is_key=True, description="Eindeutige Kennung der Zeile."),
		Column(name="Anlagennummer", description="Anlage, zu der die Abschreibung gehoert."),
		Column(name="Datum", type=DATE, description="Datum der Abschreibung."),
		_amount("Betrag", "Abschreibungsbetrag."),
		_amount("KumulierterBetrag", "Kumulierte Abschreibung nach dieser Zeile."),
		Column(name="Belegnummer", description="Buchungsbeleg der Abschreibung, falls gebucht."),
		Column(
			name="Gebucht",
			description="Kennzeichen, ob die Abschreibung bereits gebucht ist.",
			maps=MAP_YES_NO,
		),
		Column(name="Finanzbuch", description="Finanzbuch der Abschreibungsreihe."),
	),
	foreign_keys=(ForeignKey(columns=("Anlagennummer",), references="Anlagegueter"),),
)

#: Finanzbuchhaltung: journal, chart of accounts and the master data it refers to.
#: The journal runs first because it defines which accounts and parties are used.
MVP_TABLES: tuple[Table, ...] = (JOURNAL, ACCOUNTS, CUSTOMERS, SUPPLIERS, TAXES)

#: Document level, payments and open items (SPEC.md, stage 2).
STAGE_2_TABLES: tuple[Table, ...] = (
	SALES_INVOICES,
	SALES_INVOICE_ITEMS,
	PURCHASE_INVOICES,
	PURCHASE_INVOICE_ITEMS,
	PAYMENTS,
	PAYMENT_ALLOCATIONS,
	OPEN_ITEMS_CUSTOMERS,
	OPEN_ITEMS_SUPPLIERS,
)

#: Anlagenbuchhaltung (SPEC.md, stage 3).
STAGE_3_TABLES: tuple[Table, ...] = (ASSETS, DEPRECIATIONS)

ALL_TABLES: tuple[Table, ...] = MVP_TABLES + STAGE_2_TABLES + STAGE_3_TABLES


def get_tables() -> tuple[Table, ...]:
	"""Return the tables of an export package, in file order.

	The scope is deliberately not configurable: the tax audit defines what it
	needs, not the taxpayer (SPEC.md, stage 2).
	"""
	return ALL_TABLES


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
