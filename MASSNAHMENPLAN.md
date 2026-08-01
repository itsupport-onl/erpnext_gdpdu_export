# Maßnahmenplan `erpnext_gdpdu_export`

Arbeitsgrundlage für die Umsetzung mit Claude Code. Jede Phase endet mit einer
prüfbaren **Definition of Done (DoD)**. Reihenfolge einhalten; keine Phase
beginnen, deren Vorgänger-DoD nicht erfüllt ist.

## Phase 0 — Repository & Scaffold  *(dieses Commit)*

- [x] Repo-Struktur nach Muster `qonto_banking` (README, SPEC, CONTRIBUTING-Verweis,
      CI-Platzhalter, pre-commit, pyproject, license)
- [x] Konzept (KONZEPT.md), Maßnahmenplan (diese Datei), CLAUDE.md
- [x] Minimales Frappe-App-Gerüst (hooks.py, modules.txt), installierbar per
      `bench get-app`
- [ ] Privates Repo `itsupport-onl/erpnext_gdpdu_export` angelegt und gepusht (Jan)

**DoD:** `bench get-app <repo> && bench --site dev.localhost install-app
erpnext_gdpdu_export` läuft fehlerfrei durch.

## Phase 1 — Schema-Definition & Formatkern

1. `gdpdu/schema.py`: deklarative Tabellendefinitionen (MVP-Tabellen aus
   KONZEPT.md §3) als Datenklassen: Tabellenname, URL, Beschreibung, Spalten
   (Name, Typ AlphaNumeric/Numeric/Date, MaxLength, Accuracy, Format),
   PrimaryKeys, ForeignKeys
2. `gdpdu/csv_writer.py`: schreibt aus Iterables von Dicts eine
   VariableLength-CSV nach Formatfestlegung (UTF-8, `;`, CRLF, `"`-Quoting mit
   Verdopplung, Kopfzeile, Beträge mit Komma und 2 Nachkommastellen, Datum
   YYYYMMDD, negatives Vorzeichen vorangestellt)
3. `gdpdu/index_xml.py`: erzeugt die index.xml **ausschließlich aus den
   Schema-Definitionen** (DataSet → DataSupplier → Media → Table je Schema);
   DOCTYPE-Referenz auf `gdpdu-01-08-2002.dtd`; XML-Sonderzeichen escapen
4. Unit-Tests für 1–3 (ohne Datenbank): Grenzfälle Umlaute, `;` und `"` im Text,
   negative Beträge, leere Felder, Datumsformate

**DoD:** `bench run-tests --app erpnext_gdpdu_export` grün; generierte index.xml
validiert gegen die DTD (Test mit lxml, DTD aus `resources/`).

**Status: erledigt.** Elementreihenfolge aus der Original-DTD in SPEC.md
dokumentiert und im Generator umgesetzt; Unit-Tests laufen zusätzlich ohne Site
(`python -m unittest discover -s erpnext_gdpdu_export/tests -t .`).

## Phase 2 — Datenextraktion (MVP-Tabellen)

1. `gdpdu/extractors/` — je Tabelle ein Extractor mit einheitlichem Interface
   `iter_rows(company, from_date, to_date) -> Iterator[dict]`:
   - `journal.py`: GL Entry (is_cancelled=0), sortiert nach posting_date,
     creation; Felder lt. SPEC.md; chunked Query (keine Volllast)
   - `accounts.py`: Kontenplan der Company; Warnung bei fehlender account_number
   - `customers.py` / `suppliers.py`: Stamm + primäre Adresse (Dynamic Link)
   - `taxes.py`: Steuerkonten/-sätze aus Tax Templates
2. Prüfprotokoll-Sammler: Zeilenzahlen, Summe Soll/Haben (müssen gleich sein),
   Warnliste
3. Tests je Extractor gegen Frappe-Test-Fixtures (Company, Konten, ein
   Buchungssatz-Set inkl. Personalkosten-Konten, ein Debitor/Kreditor)

**DoD:** Alle Extractor-Tests grün; Soll=Haben-Invariante im Test nachgewiesen.

**Status: erledigt.** Journal mit Keyset-Pagination (5.000 Zeilen je Abfrage);
Debitoren/Kreditoren nur mit Bewegung im Zeitraum; Warnungen für fehlende
Kontonummern, doppelte Kontoschlüssel, fehlende Anschriften und Steuersätze.

## Phase 3 — DocType, Background Job, Paketierung

1. DocType **GDPdU Export** lt. KONZEPT.md §4 (Felder, Status, Rollen:
   System Manager, Accounts Manager; Track Changes an)
2. `gdpdu/package.py`: Orchestrierung Extraktion → CSVs → index.xml → DTD →
   ZIP → privates File-Attachment; Fortschritt via `frappe.publish_progress`
3. Button „Export erstellen" → `frappe.enqueue(..., queue="long")`;
   Fehlerbehandlung: Status Failed + Traceback ins Error Log, verständliche
   Meldung ins Dokument
4. Integrationstest: kompletter Lauf auf Fixtures, ZIP-Inhalt geprüft

**DoD:** Im Desk: Export anlegen, erstellen, ZIP herunterladen; Paket enthält
index.xml (DTD-valide), DTD, alle MVP-CSVs; Protokoll zeigt plausible Zahlen.

**Status: erledigt.** Auf einer ERPNext-v15-Site (Docker) durchgespielt: Export
im Desk angelegt, Hintergrund-Job erzeugt, Status wechselt selbsttätig auf
„Fertig", ZIP enthält index.xml (gegen die Original-DTD validiert), DTD, alle
fünf MVP-CSVs, Prüfprotokoll und LIESMICH; Soll = Haben im Protokoll.
Zusätzlich: DTD-Upload in den Settings, Arbeitsbereich, Statusfarben in der
Liste, Polling-Fallback für Setups ohne Websocket.

## Phase 4 — Stufe-2-Tabellen (fester Bestandteil des Exports)

1. Extractors + Schemata: Ausgangs-/Eingangsrechnungen inkl. Positionen,
   Zahlungen inkl. Zuordnung, OPOS zum Stichtag
2. ForeignKeys der Belegebene in index.xml
3. Tests analog Phase 2/3

**DoD:** Vollpaket mit Stufe 2 erzeugt, DTD-valide, Tests grün.

**Status: erledigt.** Abweichung vom ursprünglichen Plan: **keine Checkboxen** —
der Umfang ist nicht Wahl des Steuerpflichtigen (Begründung in KONZEPT.md §3).
13 Tabellen im Paket, DTD-valide, 91 Tests grün auf v15 *und* v16. OPOS werden
aus dem Journal zum Stichtag gerechnet (`against_voucher`), nicht aus dem
tagesaktuellen Saldo.

## Phase 4b — Anlagenbuchhaltung (Stufe 3)

1. Schemata + Extractor: Anlagenverzeichnis zum Stichtag und Abschreibungszeilen
   des Zeitraums, Konten aus der Anlagenklasse
2. Tests analog Phase 4

**DoD:** Anlagentabellen im Vollpaket, DTD-valide, Tests grün.

**Status: erledigt.** 15 Tabellen im Paket. Der Buchwert wird zum Stichtag aus
Anschaffungskosten und tatsächlich gebuchter Abschreibung gerechnet; geplante,
noch nicht gebuchte Zeilen sind über die Spalte `Gebucht` erkennbar. ERPNext hat
das Feld der Anschaffungskosten zwischen v15 (`gross_purchase_amount`) und v16
(`net_purchase_amount`) umbenannt — der Extractor ermittelt es zur Laufzeit.
94 Tests grün auf v15 und v16.

## Phase 5 — Doku, Recht, Release

1. README final (deutsch): Zweck, „Was die App nie tut", Setup, Bedienung,
   DSGVO-Hinweis, **Haftungsausschluss** (MIT-Disclaimer + Klartext-Abschnitt:
   keine Steuerberatung, keine Garantie der Prüfungsanerkennung, pre-1.0)
2. Offenen Punkt DTD-Redistribution entscheiden (KONZEPT.md §7.1)
3. CHANGELOG, Version 0.1.0 taggen, CI final (Lint + Tests auf Frappe v15)
4. Repo public stellen; GitHub Topics: erpnext, frappe, gdpdu, gobd,
   betriebspruefung, idea, accounting, germany. In den ERPNext-Issues
   frappe/erpnext#36344 (GDPdU report) und #19328 (Germany localization)
   verlinken — dort sitzt die wartende Zielgruppe. Kurzer Blick auf das
   Odoo-GoBD-Modul (initos) als Wettbewerbs-/Feature-Vergleich fürs README
5. Community-Testphase: Export an Steuerberater/Prüfer zur IDEA-Verprobung;
   Ergebnis als Issue-Meilenstein „IDEA-verified" dokumentieren

**DoD:** Public Repo, Release v0.1.0, README vollständig, mindestens eine
externe Verprobungszusage.

## Arbeitsweise mit Claude Code

- Pro Phase ein Branch (`phase-1-format-core`, …), PR gegen `main`
- Vor jeder Implementierung SPEC.md lesen; Abweichungen zuerst in SPEC.md ändern
- Commits klein, Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`)
- Nach jeder Phase CHANGELOG-Eintrag
