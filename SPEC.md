# SPEC — Datenmodell und Feldmapping

Verbindliche Referenz für Implementierung und Tests. Formatregeln: siehe
KONZEPT.md §2. Änderungen am Export **immer zuerst hier** nachziehen.

Alle Tabellen: VariableLength, UTF-8, `;`, CRLF, Kopfzeile (Range From=2),
DecimalSymbol `,`, DigitGroupingSymbol `.` (nur Deklaration — Daten enthalten
keine Tausendertrenner), Datum `YYYYMMDD`, Beträge Numeric Accuracy 2.

## journal.csv — Buchungsjournal

Quelle: `GL Entry`, Filter `company`, `posting_date` in [von, bis],
`is_cancelled = 0`. Sortierung: `posting_date, creation, name`.

| Spalte | Typ | Quelle (GL Entry) | Bemerkung |
|---|---|---|---|
| JournalID | AlphaNumeric, PK | `name` | eindeutig |
| Buchungsdatum | Date YYYYMMDD | `posting_date` | |
| Belegdatum | Date YYYYMMDD | `posting_date` | GL Entry führt kein eigenes Belegdatum; Verfeinerung mit Stufe 2 |
| Belegart | AlphaNumeric | `voucher_type` | Sales Invoice, Journal Entry, … |
| Belegnummer | AlphaNumeric | `voucher_no` | Verknüpfung zur Belegebene |
| Konto | AlphaNumeric, FK→kontenplan | `account` → `Account.account_number` (Fallback: Kontoname) | |
| Kontobezeichnung | AlphaNumeric | `Account.account_name` | Redundanz gewollt (Prüferkomfort) |
| Soll | Numeric(2) | `debit` | in Company-Währung |
| Haben | Numeric(2) | `credit` | |
| Waehrung | AlphaNumeric | Company default currency | konstant je Export |
| GegenparteiTyp | AlphaNumeric | `party_type` | Customer/Supplier/Employee/leer |
| Gegenpartei | AlphaNumeric | `party` | siehe Hinweis unten |
| Gegenkonto | AlphaNumeric | `against` | Sammelangabe; Kontonamen werden auf Kontoschlüssel übersetzt, mehrere durch Komma getrennt. ERPNext trägt bei Buchungen auf Personenkonten dort die Gegenpartei statt eines Kontos ein — Werte werden unverändert übernommen und in der Spaltenbeschreibung erläutert |
| Buchungstext | AlphaNumeric | `remarks` | bereinigt: CR/LF → Leerzeichen |
| Kostenstelle | AlphaNumeric | `cost_center` | |
| ErfasstAm | Date YYYYMMDD | `creation` | |
| ErfasstUm | AlphaNumeric + Map HH:MM:SS | `creation` (Zeitanteil) | Zeit-Typ gem. Standard v1.6 |
| ErfasstVon | AlphaNumeric | `owner` | GoBD: Nachvollziehbarkeit |

Invariante: Σ Soll = Σ Haben über den gesamten Export (Test + Prüfprotokoll).

**ForeignKeys des Journals.** Deklariert wird nur `Konto → Kontenplan`. Für
`Gegenpartei` ist *kein* ForeignKey deklariert: die Spalte zeigt je nach
`GegenparteiTyp` auf `debitoren` oder `kreditoren` (und bei `Employee` auf keine
der beiden Tabellen). Ein FK auf genau eine Tabelle wäre für die jeweils andere
Hälfte der Zeilen referenziell unauflösbar. Die Zuordnung steht stattdessen in
der Spaltenbeschreibung der index.xml.

**Eindeutigkeit des Kontoschlüssels.** `Konto` ist Primärschlüssel des
Kontenplans. Führen zwei Konten auf denselben Schlüssel (gleiche Kontonummer
oder — beim Fallback — gleiche Bezeichnung), verwendet der Export für das
zweite Konto den vollständigen ERPNext-Kontonamen und protokolliert eine
Warnung. Journal und Kontenplan benutzen dieselbe Zuordnung, bleiben also
konsistent.

## kontenplan.csv — Sachkonten

Quelle: `Account`, Filter `company`. Nur Konten mit Bewegungen im Zeitraum
**plus** deren Elternkonten? → Nein: vollständiger Kontenplan der Company
(einfacher, prüferfreundlich). `is_group` wird mit exportiert.

| Spalte | Typ | Quelle | Bemerkung |
|---|---|---|---|
| Konto | AlphaNumeric, PK | `account_number`, Fallback `account_name` | Warnung im Protokoll bei Fallback |
| Kontobezeichnung | AlphaNumeric | `account_name` | |
| Kontotyp | AlphaNumeric | `account_type` | |
| Wurzeltyp | AlphaNumeric | `root_type` | Asset/Liability/Income/Expense/Equity |
| IstGruppe | AlphaNumeric + Map 0→Nein,1→Ja | `is_group` | Map-Element demonstrieren |
| Waehrung | AlphaNumeric | `account_currency` | |

## debitoren.csv / kreditoren.csv

Quelle: `Customer` / `Supplier` (alle mit Journalbewegung im Zeitraum),
primäre Adresse via Dynamic Link (`customer_primary_address` bzw. erste
Address mit `is_primary_address`).

| Spalte | Typ | Quelle |
|---|---|---|
| Kennung | AlphaNumeric, PK | `name` |
| Name | AlphaNumeric | `customer_name` / `supplier_name` |
| Strasse | AlphaNumeric | `Address.address_line1` (+2) |
| PLZ | AlphaNumeric | `Address.pincode` |
| Ort | AlphaNumeric | `Address.city` |
| Land | AlphaNumeric | `Address.country` |
| UStIdNr | AlphaNumeric | `tax_id` |

## steuerkennzeichen.csv

Quelle: Steuerkonten (`Account.account_type = 'Tax'`) angereichert um Sätze aus
`Sales Taxes and Charges Template` / `Purchase Taxes and Charges Template`.

| Spalte | Typ | Quelle |
|---|---|---|
| Steuerkonto | AlphaNumeric, PK, FK→kontenplan | Account |
| Bezeichnung | AlphaNumeric | `account_name` |
| Satz | Numeric(2) | Template-Rate, sonst `Account.tax_rate` |
| Richtung | AlphaNumeric | `Sales`, `Purchase` oder `Sales+Purchase` (Map erklärt die Werte) |

## index.xml — Rahmen

```
DataSet
├─ Version        1.0 (Version der Datenlieferung, nicht des Standards)
├─ DataSupplier   Name=Company, Location=Company-Adresse Ort,
│                 Comment="GoBD-Datentraegerueberlassung <Zeitraum>, erstellt
│                 mit erpnext_gdpdu_export <version>"
└─ Media Name="Export"
   └─ je Tabelle: Table{URL, Name, Description, Validity(Range=Zeitraum,
      Format YYYYMMDD), UTF8, DecimalSymbol, DigitGroupingSymbol,
      Range From=2, VariableLength{Keys, Columns, ForeignKeys}}
```

DOCTYPE: `<!DOCTYPE DataSet SYSTEM "gdpdu-01-08-2002.dtd">` — Dateiname der DTD
bleibt aus Kompatibilitätsgründen der historische, auch für Standard v1.6.

Elementreihenfolge (bindend, aus der DTD):

```
Table          (URL, Name?, Description?, Validity?, UTF8?,
                (DecimalSymbol, DigitGroupingSymbol)?, SkipNumBytes?, Range?,
                Epoch?, (VariableLength | FixedLength))
VariableLength (ColumnDelimiter?, RecordDelimiter?, TextEncapsulator?,
                ((VariablePrimaryKey+, VariableColumn*) | (VariableColumn+)),
                ForeignKey*)
VariableColumn (Name, Description?, (Numeric | (AlphaNumeric, MaxLength?) | Date), Map*)
DataSupplier   (Name, Location, Comment)   — alle drei Pflicht
ForeignKey     (Name+, References)         — References = <Name> der Zieltabelle
```

Daraus folgt: **Schlüsselspalten müssen die ersten Spalten der CSV sein**, weil
`VariablePrimaryKey` positionsbezogen vor `VariableColumn` steht. Das Schema
erzwingt das (`Table.__post_init__`).

`RecordDelimiter` wird als `&#13;&#10;` geschrieben — ein literales CR würde von
jedem XML-Parser zu LF normalisiert.

Beschreibungstexte in der index.xml sind bewusst ASCII (keine Umlaute), damit
ältere IDEA-Versionen nicht darüber stolpern; die Nutzdaten in den CSVs sind
UTF-8 mit Umlauten.

## Paketinhalt

| Datei | Zweck | in index.xml deklariert |
|---|---|---|
| `index.xml` | Beschreibung aller Tabellen | — |
| `gdpdu-01-08-2002.dtd` | DTD (Fremdartefakt, siehe KONZEPT.md §7.1) | — |
| `*.csv` | Nutzdaten | ja |
| `pruefprotokoll.txt` | Zeilenzahlen, Summen, Warnungen | nein |
| `LIESMICH.txt` | Klartext-Erläuterung für Anwender und Prüfer | nein |

## Stufe 2 — Belegebene, Zahlungen, offene Posten

**Nicht abwählbar.** Die GoBD (Rz. 159) verlangen die Daten der
Finanzbuchhaltung *und aller Vor- und Nebensysteme mit aufzeichnungs- und
aufbewahrungspflichtigen Unterlagen*; Aus- und Eingangsrechnungen sind nach
§ 147 Abs. 1 AO aufbewahrungspflichtig. Der Umfang ist damit nicht Wahl des
Steuerpflichtigen. Tabellen ohne Daten werden als CSV mit reiner Kopfzeile
exportiert (z. B. wenn ein Betrieb keine Rechnungen in ERPNext schreibt).

Beträge: Spalten ohne Zusatz stehen in **Belegwährung**, Spalten mit dem Zusatz
`…Firmenwaehrung` in der Währung des Unternehmens (dieselbe wie im Journal).

### ausgangsrechnungen.csv

Quelle: `Sales Invoice`, Filter `company`, `docstatus = 1`, `posting_date` in
[von, bis]. Sortierung: `posting_date, name`.

| Spalte | Typ | Quelle | Bemerkung |
|---|---|---|---|
| Belegnummer | AlphaNumeric, PK | `name` | identisch mit `journal.Belegnummer` |
| Belegdatum | Date | `posting_date` | |
| Faelligkeit | Date | `due_date` | |
| Debitor | AlphaNumeric, FK→Debitoren | `customer` | |
| DebitorName | AlphaNumeric | `customer_name` | |
| Waehrung | AlphaNumeric | `currency` | |
| Wechselkurs | Numeric(6) | `conversion_rate` | 1 bei Firmenwährung |
| Netto | Numeric(2) | `net_total` | |
| Steuer | Numeric(2) | `total_taxes_and_charges` | |
| Brutto | Numeric(2) | `grand_total` | |
| NettoFirmenwaehrung | Numeric(2) | `base_net_total` | |
| SteuerFirmenwaehrung | Numeric(2) | `base_total_taxes_and_charges` | |
| BruttoFirmenwaehrung | Numeric(2) | `base_grand_total` | |
| IstGutschrift | AlphaNumeric + Map 0→Nein,1→Ja | `is_return` | |
| Status | AlphaNumeric | `status` | |
| Buchungstext | AlphaNumeric | `remarks` | CR/LF bereinigt |
| ErfasstAm / ErfasstUm / ErfasstVon | Date / AlphaNumeric / AlphaNumeric | `creation`, `owner` | wie Journal |

### ausgangsrechnungen_positionen.csv

Quelle: `Sales Invoice Item` der oben exportierten Belege.

| Spalte | Typ | Quelle |
|---|---|---|
| PositionsID | AlphaNumeric, PK | `name` (Zeilen-ID) |
| Belegnummer | AlphaNumeric, FK→Ausgangsrechnungen | `parent` |
| Position | Numeric(0) | `idx` |
| Artikel | AlphaNumeric | `item_code` |
| Bezeichnung | AlphaNumeric | `item_name` |
| Menge | Numeric(3) | `qty` |
| Einheit | AlphaNumeric | `uom` |
| Einzelpreis | Numeric(2) | `rate` |
| Netto | Numeric(2) | `net_amount` |
| NettoFirmenwaehrung | Numeric(2) | `base_net_amount` |
| Ertragskonto | AlphaNumeric, FK→Kontenplan | `income_account` |
| Kostenstelle | AlphaNumeric | `cost_center` |
| Steuervorlage | AlphaNumeric | `item_tax_template` |

### eingangsrechnungen.csv

Quelle: `Purchase Invoice`, Filter analog. Zusätzlich zur Ausgangsseite:

| Spalte | Typ | Quelle | Bemerkung |
|---|---|---|---|
| Kreditor | AlphaNumeric, FK→Kreditoren | `supplier` | |
| KreditorName | AlphaNumeric | `supplier_name` | |
| LieferantenBelegnummer | AlphaNumeric | `bill_no` | Rechnungsnummer des Lieferanten |
| LieferantenBelegdatum | Date | `bill_date` | |

Übrige Spalten wie `ausgangsrechnungen.csv`.

### eingangsrechnungen_positionen.csv

Wie die Ausgangsseite, statt `Ertragskonto` das **Aufwandskonto**
(`expense_account`, FK→Kontenplan).

### zahlungen.csv

Quelle: `Payment Entry`, Filter `company`, `docstatus = 1`, `posting_date` in
[von, bis].

| Spalte | Typ | Quelle | Bemerkung |
|---|---|---|---|
| Zahlungsnummer | AlphaNumeric, PK | `name` | |
| Buchungsdatum | Date | `posting_date` | |
| Zahlungsart | AlphaNumeric + Map | `payment_type` | Receive→Eingang, Pay→Ausgang, Internal Transfer→Umbuchung |
| GegenparteiTyp | AlphaNumeric | `party_type` | |
| Gegenpartei | AlphaNumeric | `party` | siehe Hinweis beim Journal |
| KontoVon | AlphaNumeric, FK→Kontenplan | `paid_from` | |
| KontoNach | AlphaNumeric, FK→Kontenplan | `paid_to` | |
| Betrag | Numeric(2) | `paid_amount` | |
| Waehrung | AlphaNumeric | `paid_from_account_currency` | |
| BetragFirmenwaehrung | Numeric(2) | `base_paid_amount` | |
| Referenz | AlphaNumeric | `reference_no` | Beleg-/Transaktionsnummer der Bank |
| Referenzdatum | Date | `reference_date` | |
| Buchungstext | AlphaNumeric | `remarks` | |
| ErfasstAm / ErfasstUm / ErfasstVon | | `creation`, `owner` | |

### zahlungszuordnungen.csv

Quelle: `Payment Entry Reference` der exportierten Zahlungen — beantwortet die
Prüferfrage „welche Zahlung tilgt welche Rechnung".

| Spalte | Typ | Quelle |
|---|---|---|
| ZuordnungsID | AlphaNumeric, PK | `name` |
| Zahlungsnummer | AlphaNumeric, FK→Zahlungen | `parent` |
| Belegart | AlphaNumeric | `reference_doctype` |
| Belegnummer | AlphaNumeric | `reference_name` |
| ZugeordneterBetrag | Numeric(2) | `allocated_amount` |

### opos_debitoren.csv / opos_kreditoren.csv

Offene Posten **zum Stichtag „bis"**, aus dem Journal gerechnet (nicht aus dem
tagesaktuellen Saldo): Summe `debit - credit` je Partei, Beleg und Konto über
alle GL Entries mit `posting_date <= bis`, `is_cancelled = 0` und
`party_type = Customer` bzw. `Supplier` auf Konten mit `account_type`
`Receivable` bzw. `Payable`. Gruppiert wird nach `against_voucher` (ERPNext
verweist damit von Zahlung/Gutschrift auf die Ursprungsrechnung), ersatzweise
nach `voucher_no`. Zeilen mit Saldo 0,00 entfallen.

| Spalte | Typ | Quelle | Bemerkung |
|---|---|---|---|
| Partei | AlphaNumeric, PK, FK→Debitoren/Kreditoren | `party` | |
| Beleg | AlphaNumeric, PK | `against_voucher`, ersatzweise `voucher_no` | |
| Konto | AlphaNumeric, PK, FK→Kontenplan | `account` | |
| Belegart | AlphaNumeric | `against_voucher_type`, ersatzweise `voucher_type` | |
| Belegdatum | Date | frühestes `posting_date` der Gruppe | |
| OffenerBetrag | Numeric(2) | Debitoren: Σ(Soll−Haben), Kreditoren: Σ(Haben−Soll) | positiv = offen |
| Waehrung | AlphaNumeric | Firmenwährung | |
| Stichtag | Date | Exportende „bis" | in jeder Zeile, damit der Bezug eindeutig ist |

Der Beschreibungsstandard erlaubt mehrere `VariablePrimaryKey`-Spalten; die drei
Schlüsselspalten stehen deshalb am Anfang der Datei.

## Stufe 3 — Anlagenbuchhaltung

Ebenfalls **nicht abwählbar**: Die GoBD (Rz. 159) nennen die Anlagenbuchhaltung
ausdrücklich neben der Finanzbuchhaltung.

### anlagegueter.csv

Quelle: `Asset`, Filter `company`, `docstatus = 1`, `purchase_date <= bis` und
(kein Abgang **oder** Abgang `>= von`) — also alle Anlagen, die im Zeitraum zum
Bestand gehörten, inklusive der Abgänge. Abschreibungsparameter aus der ersten
Zeile von `Asset Finance Book`, Konten aus `Asset Category Account` der Company.

| Spalte | Typ | Quelle | Bemerkung |
|---|---|---|---|
| Anlagennummer | AlphaNumeric, PK | `name` | |
| Bezeichnung | AlphaNumeric | `asset_name` | |
| Anlagenklasse | AlphaNumeric | `asset_category` | |
| Artikel | AlphaNumeric | `item_code` | |
| Anschaffungsdatum | Date | `purchase_date` | |
| Inbetriebnahme | Date | `available_for_use_date` | Beginn der Nutzung |
| Anschaffungskosten | Numeric(2) | `gross_purchase_amount` (v15) bzw. `net_purchase_amount` (v16) | dasselbe Feld, in v16 umbenannt |
| AnschaffungskostenGesamt | Numeric(2) | `total_asset_cost` | inkl. nachträglicher Anschaffungskosten |
| Menge | Numeric(3) | `asset_quantity` | |
| Abschreibungsmethode | AlphaNumeric | `Asset Finance Book.depreciation_method` | |
| AnzahlAbschreibungen | Numeric(0) | `total_number_of_depreciations` | |
| IntervallMonate | Numeric(0) | `frequency_of_depreciation` | 12 = jährlich |
| Abschreibungsbeginn | Date | `depreciation_start_date` | |
| Restwert | Numeric(2) | `expected_value_after_useful_life` | |
| AbschreibungEroeffnung | Numeric(2) | `opening_accumulated_depreciation` | Übernahme aus Altsystem |
| KumulierteAbschreibung | Numeric(2) | Eröffnung + gebuchte AfA bis Stichtag | nur Zeilen mit Buchungsbeleg |
| BuchwertStichtag | Numeric(2) | AnschaffungskostenGesamt − KumulierteAbschreibung | |
| Status | AlphaNumeric | `status` | |
| Abgangsdatum | Date | `disposal_date` | |
| Kostenstelle | AlphaNumeric | `cost_center` | |
| Standort | AlphaNumeric | `location` | |
| Anlagenkonto | AlphaNumeric, FK→Kontenplan | `fixed_asset_account` | |
| AfAKonto | AlphaNumeric, FK→Kontenplan | `depreciation_expense_account` | |
| KumAfAKonto | AlphaNumeric, FK→Kontenplan | `accumulated_depreciation_account` | |
| Stichtag | Date | Exportende „bis" | Bezug von KumulierteAbschreibung und BuchwertStichtag |
| ErfasstAm / ErfasstUm / ErfasstVon | | `creation`, `owner` | |

### abschreibungen.csv

Quelle: `Depreciation Schedule` (Kindtabelle von `Asset Depreciation Schedule`,
`docstatus = 1`, `company`), Filter `schedule_date` in [von, bis]. Geplante, noch
nicht gebuchte Zeilen sind enthalten und über `Gebucht` erkennbar.

| Spalte | Typ | Quelle |
|---|---|---|
| AbschreibungsID | AlphaNumeric, PK | `name` der Zeile |
| Anlagennummer | AlphaNumeric, FK→Anlagegueter | `Asset Depreciation Schedule.asset` |
| Datum | Date | `schedule_date` |
| Betrag | Numeric(2) | `depreciation_amount` |
| KumulierterBetrag | Numeric(2) | `accumulated_depreciation_amount` |
| Belegnummer | AlphaNumeric | `journal_entry` |
| Gebucht | AlphaNumeric + Map 0→Nein,1→Ja | abgeleitet aus `journal_entry` |
| Finanzbuch | AlphaNumeric | `Asset Depreciation Schedule.finance_book` |

### ForeignKeys der Stufe 2 und 3

`positionen.Belegnummer` → Rechnung · `positionen.Ertragskonto`/`Aufwandskonto`
→ Kontenplan · `rechnung.Debitor`/`Kreditor` → Debitoren/Kreditoren ·
`zahlungen.KontoVon`/`KontoNach` → Kontenplan · `zahlungszuordnungen.Zahlungsnummer`
→ Zahlungen · `opos.Konto` → Kontenplan · `opos.Partei` → Debitoren bzw. Kreditoren.

`anlagegueter.Anlagenkonto`/`AfAKonto`/`KumAfAKonto` → Kontenplan ·
`abschreibungen.Anlagennummer` → Anlagegueter.

Bewusst **kein** ForeignKey von `journal.Belegnummer` auf die Rechnungstabellen:
das Journal enthält alle Belegarten, ein FK wäre für Zahlungen, Buchungssätze
usw. referenziell unauflösbar. `zahlungszuordnungen.Belegnummer` bleibt aus dem
gleichen Grund ohne FK (Ziel kann Ausgangs- oder Eingangsrechnung sein).
