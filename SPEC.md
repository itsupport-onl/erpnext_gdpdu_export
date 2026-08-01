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

## Stufe 2 (Belegebene) — Skizze

`ausgangsrechnungen.csv` (Sales Invoice, docstatus=1): Belegnummer PK,
Datum, Debitor FK, Netto, Steuer, Brutto, Währung, Fälligkeit, Status.
`ausgangsrechnungen_positionen.csv`: Belegnummer FK, Position, Artikel,
Menge, Einzelpreis, Netto, Ertragskonto FK→kontenplan.
Eingangsseite analog. `zahlungen.csv` (Payment Entry): Zahlungsnummer PK,
Datum, Richtung, Partei, Betrag, Referenzen. OPOS: AR/AP zum Stichtag „bis".
Detaillierung erfolgt zu Beginn von Phase 4 in dieser Datei.
