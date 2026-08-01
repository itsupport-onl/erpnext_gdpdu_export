# Konzept: GDPdU/GoBD-Export für ERPNext

**Projekt:** `erpnext_gdpdu_export` · **Träger:** itsupport.online (Coozinha UG, Berlin) · **Lizenz:** MIT
**Status:** Konzeptphase · **Stand:** 2026-08-01

## 1. Ziel

Eine Frappe/ERPNext-App, die die Finanzbuchhaltungsdaten einer ERPNext-Instanz als
**Datenträgerüberlassung (Z3-Zugriff, § 147 Abs. 6 AO)** im Format des
**Audicon-Beschreibungsstandards** (aktuelle Version 1.6 vom 01.03.2019, GDPdU/GoBD)
exportiert — direkt einlesbar in die Prüfsoftware **IDEA** der Finanzverwaltung.

Zielgruppe: deutsche Unternehmen, die ERPNext für die Finanzbuchhaltung nutzen oder
nutzen wollen. Der fehlende Betriebsprüfungs-Export ist eine der größten
Adoptionshürden für ERPNext in Deutschland; dieses Projekt beseitigt sie als
Open-Source-Baustein.

## 2. Formatgrundlage

Referenzen:
- *Beschreibungsstandard für die Datenträgerüberlassung*, Audicon GmbH, Version 1.6
  (01.03.2019): https://www.caseware.net/fileadmin/audicon/media/allgemeine_bilder/Beschreibungsstandard-GDPdU-01-03-2019.pdf
  (Portal: https://www.caseware.net/ihr-know-how-portal-zum-beschreibungsstandard/)
- BMF, *GoBD* vom 28.11.2019 (Rz. 156 ff.: Datenzugriff) und BMF, *Ergänzende
  Informationen zur Datenträgerüberlassung* (14.11.2014) — offizielle Primärquellen
  der Finanzverwaltung zur Datensatzbeschreibung
- DSAG-Handlungsempfehlung GoBD/GDPdU v4.01 (Praxis-/Prüfungssicht):
  https://www.dsag.de/wp-content/uploads/2021/12/dsag_handlungsempfehlung_gobd_gdpdu_v4.01_0.pdf
- ERPNext-Community-Bedarf: https://github.com/frappe/erpnext/issues/36344 und
  Sammel-Issue Germany Localization #19328

Hinweis zur Verbindlichkeit: Das XML-Beschreibungsformat ist für Steuerpflichtige
nicht gesetzlich bindend; es ist der vom BMF zur Automatisierung der
IDEA-Schnittstelle propagierte und praktisch etablierte Standard. Diese App setzt
ihn bewusst als De-facto-Standard um.

Ein Exportpaket (ZIP) enthält:

| Bestandteil | Inhalt |
|---|---|
| `index.xml` | Maschinenlesbare Beschreibung aller Tabellen, Spalten, Datentypen, Verknüpfungen; validiert gegen die DTD |
| `gdpdu-01-08-2002.dtd` | Unveränderte Original-DTD von Audicon (muss im selben Verzeichnis liegen) |
| `*.csv` | Nutzdaten, Format **VariableLength** |

Technische Festlegungen (alle explizit in der index.xml deklariert, keine
stillschweigenden Defaults):

| Parameter | Festlegung | Begründung |
|---|---|---|
| Dateiformat | VariableLength (CSV) | einfacher als FixedLength, von IDEA voll unterstützt |
| Codepage | UTF-8 (`<UTF8/>`) | Umlaute in Namen/Buchungstexten |
| Spaltentrenner | `;` (Default) | |
| Satztrenner | CRLF (Default) | |
| Texteinschluss | `"` (Default); `"` in Daten wird verdoppelt | |
| Kopfzeile | ja, in jeder CSV; übersprungen per `<Range><From>2</From></Range>` | menschenlesbar + maschinenlesbar |
| Dezimaltrenner | `,` · Tausendertrenner: keiner in den Daten | deutsche Konvention, IDEA-Default |
| Beträge | `Numeric`, `<Accuracy>2</Accuracy>`; negativ mit vorangestelltem `-` ohne Leerzeichen | Formatvorgabe |
| Datum | `YYYYMMDD`, deklariert per `<Format>` | sortierfähig, eindeutig |
| Zeit | AlphaNumeric mit `<Map><From>HH:MM:SS</From><To>HH:MM:SS</To></Map>` | Zeit-Datentyp seit v1.6 nur so |
| Verbotene Zeichen | `" & < >` in index.xml als Entities | DTD-Vorgabe |

## 3. Exportumfang

Gegenstand des Exports ist die **gesamte Finanzbuchhaltung** der gewählten
Company im gewählten Zeitraum: das vollständige Buchungsjournal über alle Konten,
der komplette Kontenplan sowie die zugehörigen Stammdaten. Es findet keine
inhaltliche Filterung nach Kontenbereichen statt.

Abgrenzung: **Lohnabrechnungsdaten** (Abrechnungsebene: Entgeltarten,
Bruttolisten etc.) sind nicht Gegenstand — dafür existiert die Digitale
LohnSchnittstelle (DLS). Alle FiBu-Buchungen zu Personalkosten (Aufwands-,
Forderungs- und Verbindlichkeitskonten) sind als normale Bestandteile von
Journal und Kontenplan selbstverständlich enthalten.

### Tabellen (Stufe 1, MVP)

| CSV | Quelle (ERPNext DocType) | Inhalt |
|---|---|---|
| `journal.csv` | GL Entry | vollständiges Buchungsjournal des Zeitraums: alle Soll/Haben-Bewegungen, Beleg-Referenz, Gegenpartei, Kostenstelle. **Primärtabelle.** |
| `kontenplan.csv` | Account | alle Konten der Company: Nummer, Name, Typ, Wurzeltyp (Aktiva/Passiva/Ertrag/Aufwand), Währung |
| `debitoren.csv` | Customer (+ primäre Adresse) | Debitorenstamm: Kennung, Name, Anschrift, USt-IdNr., Steuernummer |
| `kreditoren.csv` | Supplier (+ primäre Adresse) | Kreditorenstamm: analog |
| `steuerkennzeichen.csv` | Account (Tax) + Tax Templates | verwendete Steuerkonten mit Steuersatz |

### Tabellen (Stufe 2) — umgesetzt, fester Bestandteil jedes Exports

| CSV | Quelle | Inhalt |
|---|---|---|
| `ausgangsrechnungen.csv` / `_positionen.csv` | Sales Invoice (+ Items) | Belegebene inkl. Positionen, Steuerbeträge |
| `eingangsrechnungen.csv` / `_positionen.csv` | Purchase Invoice (+ Items) | analog, zusätzlich Lieferantenbelegnummer |
| `zahlungen.csv` | Payment Entry | Zahlungsverkehr |
| `zahlungszuordnungen.csv` | Payment Entry Reference | welche Zahlung welchen Beleg ausgleicht |
| `opos_debitoren.csv` / `opos_kreditoren.csv` | GL Entry zum Stichtag | offene Posten, aus dem Journal gerechnet |

**Keine Abwahlmöglichkeit** (Entscheidung 01.08.2026): Die GoBD (Rz. 159)
verlangen die Daten der Finanzbuchhaltung und aller Vor- und Nebensysteme mit
aufbewahrungspflichtigen Unterlagen; Rechnungen sind nach § 147 Abs. 1 AO
aufbewahrungspflichtig. Den Umfang bestimmt die Prüfung, nicht der
Steuerpflichtige — eine Checkbox wäre für nicht-technische Anwender ein Risiko.
Tabellen ohne Daten werden als CSV mit reiner Kopfzeile geschrieben.

### Verknüpfungen (ForeignKeys in index.xml)

- `journal.Konto` → `kontenplan`
- `journal.GegenparteiTyp/Gegenpartei` → `debitoren` bzw. `kreditoren`
- Stufe 2: Belege → Journal über Belegnummer (`voucher_no`)

### Kontenrahmen

Der Beschreibungsstandard schreibt **keinen Kontenrahmen und keine
Standardkontonummern vor** — er ist inhaltlich agnostisch. Exportiert werden die
ERPNext-Kontonummern (`account_number`) und -bezeichnungen 1:1. Fehlt die
Kontonummer, wird der Kontoname verwendet und im Prüfprotokoll gewarnt.
Ein SKR03/04-Mapping ist bewusst **nicht** Teil des Scopes (Ausbaustufe).

## 4. Architektur

Frappe-App nach dem Muster von `qonto_banking` (gleiche Repo-Struktur, CI,
pre-commit, SPEC.md). ERPNext **v15 und v16** (beide verprobt, siehe
KOMPATIBILITAET.md). Keine
Python-Abhängigkeiten außerhalb des Frappe-Frameworks (Standardbibliothek: `csv`,
`xml.etree`/manuelle Serialisierung, `zipfile`).

### DocTypes

1. **GDPdU Export** (submittable=nein, normales Dokument)
   - Filter: Company (Pflicht), Zeitraum von/bis (Pflicht, Default: letztes
     abgeschlossenes Geschäftsjahr); **kein Umfangsschalter**, siehe §3
   - Statusfeld: Draft → In Progress → Completed / Failed
   - Ergebnis: ZIP als **privates** File-Attachment + Prüfprotokoll
     (Zeilenzahlen je Tabelle, Summen Soll/Haben, Warnungen)
   - Aktion „Export erstellen" startet einen **Background Job** (frappe.enqueue,
     long queue) — keine Timeouts bei großen Journalen
2. **GDPdU Export Settings** (Single, optional ab MVP+1)
   - Vorbelegungen, Rollenzuordnung

### Ablauf

```
Benutzer legt „GDPdU Export" an → wählt Company + Zeitraum → „Export erstellen"
  → Background Job:
      1. Validierung (Zeitraum, Berechtigungen, Datenbestand vorhanden?)
      2. Extraktion je Tabelle (SQL über frappe.db, chunked, nur lesend)
      3. CSV-Schreiben (UTF-8, ; , CRLF, Quoting)
      4. index.xml generieren (Spaltenlisten aus derselben Schema-Definition
         wie die CSV-Writer → eine Quelle der Wahrheit, kein Drift)
      5. DTD beilegen, ZIP packen
      6. ZIP als privates File an das Export-Dokument hängen
      7. Prüfprotokoll schreiben, Status setzen
```

### Berechtigungen & Datenschutz

- Zugriff auf DocType und Downloads: nur **System Manager** und **Accounts Manager**
- Export-ZIP immer als *private* File (kein anonymer URL-Zugriff)
- Der Export enthält personenbezogene Daten (Namen, Adressen, USt-IdNrn.) —
  README weist auf DSGVO-gerechte Übergabe hin; auch die DSAG-Handlungsempfehlung
  rät, Datenträger nur verschlüsselt zu übergeben (Verschlüsselung/Transport an
  den Prüfer liegt in Verantwortung des Nutzers, vgl. GoBD Rz. 167 f.)
- Nur Lesezugriff auf Buchhaltungsdaten; die App bucht, ändert und löscht nichts
  („What it will never do"-Abschnitt im README, analog qonto_banking)

## 5. Qualitätssicherung

- **Schema als Code:** jede Tabelle ist eine deklarative Definition (Name,
  Spalten, Typen, Accuracy, Keys, FKs) — CSV-Writer und index.xml-Generator
  konsumieren dieselbe Definition
- **Tests:** Unit-Tests je Tabelle gegen Fixtures (Mini-Buchungssatz),
  Integrationstest, der ein komplettes Paket erzeugt und
  (a) die index.xml gegen die DTD validiert (lxml ist im Frappe-Stack vorhanden),
  (b) Zeilenzahlen und Soll=Haben-Summen prüft,
  (c) Roundtrip: CSV nach index.xml-Regeln parsen und Typen prüfen
- **Kein IDEA-Zugang vorhanden:** reale Validierung als Community-Testphase —
  fertiges Paket an Steuerberater/Prüfer zur Verprobung geben; SmartV (Audicon)
  als optionaler Test, falls Zugang entsteht. Bis dahin Status „pre-1.0, nicht
  prüfungserprobt" ehrlich im README.

## 6. Abgrenzung / Ausbaustufen

Nicht im Scope (spätere Stufen): Lohnabrechnung/DLS, SKR-Mapping,
Festschreibungs-/Unveränderbarkeitsprüfungen, Verfahrensdokumentations-Template,
Z1/Z2-Zugriff, DATEV-Export.

**Anlagenbuchhaltung (Stufe 3, priorisierte Ausbaustufe):** Die GoBD (Rz. 159)
erwarten neben der Finanzbuchhaltung ausdrücklich auch die vollumfängliche
Bereitstellung der Anlagenbuchhaltung. Für Nutzer des ERPNext-Asset-Moduls
(Asset, Depreciation Schedule) ist ein Anlagen-Export daher prüfungsrelevant und
wird nach Stufe 2 als nächstes umgesetzt. Bis dahin dokumentiert das README diese
Lücke transparent.

## 7. Offene Punkte (vor v1.0 zu klären)

1. **DTD-Redistribution:** `gdpdu-01-08-2002.dtd` ist © Audicon. Sie *muss* laut
   Standard auf jedem Datenträger liegen; praktisch liefern alle
   Buchhaltungsprogramme sie mit. Vor Public-Stellung des Repos klären, ob die
   DTD eingecheckt wird oder beim ersten Export von der Audicon-Quelle geladen
   und lokal gecacht wird. (Aktueller Stand: Platzhalter + Download-Hinweis.)
2. **Haftungsausschluss:** MIT-Disclaimer + eigener deutscher Abschnitt im README
   („keine Steuerberatung, keine Gewähr für Prüfungsanerkennung"). Formulierung
   vor v1.0 juristisch gegenlesen lassen.
3. **Reale IDEA-Verprobung** (siehe 5.).
