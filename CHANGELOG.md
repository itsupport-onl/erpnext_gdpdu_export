# Changelog

## [Unreleased]

### Hinzugefügt
- Ein nach der Installation angelegtes Unternehmen erhält seinen Datensatz *GDPdU Company
  Settings* sofort: `doc_events`-Hook auf *Company* `after_insert`, der Datensatz nennt das
  Unternehmen ausdrücklich. Scheitert das Anlegen, entsteht ein Error-Log-Eintrag; das
  Unternehmen selbst wird trotzdem angelegt (ERP-087).

### Fixed
- Ein GDPdU Export und ein Datensatz GDPdU Company Settings verlangen das Unternehmen
  ausdrücklich. Frappe belegte ein leeres Feld bisher still mit dem Standardunternehmen; ein
  REST- oder MCP-Aufruf ohne `company` erzeugte so einen Export der falschen Firma (Abnahme
  ERP-020, ERP-009).
- Text in „Fertige Exporte aufbewahren“ ergibt 0 statt eines Serverfehlers (ERP-013).
- Testfixtures ergänzen das Testunternehmen in einem Geschäftsjahr, das auf andere
  Unternehmen beschränkt ist (ERP-077).
- `create_export(start=1)` liefert den Zustand nach dem Start: `status` „In Warteschlange“
  und `is_busy` true statt des Zustands vor dem Einreihen (ERP-041).
- `fiscal_years_for_company` und `get_export_scope` verlangen Leserecht auf *GDPdU Export*,
  wie alle anderen Funktionen der Schnittstelle (ERP-035).
- Frappe 16: `delete_old_exports` und `company_overview` nutzen keine SQL-Funktionen mehr in
  `order_by`/`fields` (dort seit Frappe 16 verboten); Sortierung und Zählung laufen in Python.

## [0.3.0] - 2026-11-27

### Hinzugefügt
- **Mandantenfähigkeit:** neuer DocType *GDPdU Company Settings*, genau ein Datensatz je
  Unternehmen (Mandantenname, Ort, Steuernummer, Kontenrahmen, Berater- und
  Mandantennummer, zusätzlicher Hinweis, Standardzeitraum, Aufbewahrung fertiger Exporte).
  Die Angaben stehen im `DataSupplier` der `index.xml`, im Prüfprotokoll und in der
  LIESMICH. Ohne Datensatz greift der Export wie bisher auf die Stammdaten des
  Unternehmens zurück. Patch `v0_3.create_company_settings` legt beim Update den Datensatz
  für jedes vorhandene Unternehmen aus dessen Stammdaten an.
- Ein Export, dessen Geschäftsjahr auf andere Unternehmen beschränkt ist, wird abgewiesen;
  der Standardzeitraum neuer Exporte kommt aus den Unternehmenseinstellungen.
- **Schnittstelle für REST v2 und den MCP-Server von ERPNext 16:** Modul
  `erpnext_gdpdu_export.api` mit `create_export`, `start_export`, `get_export_status`,
  `verify_export`, `list_exports`, `download_package`, `delete_old_exports`,
  `company_overview`, `fiscal_years_for_company`, `list_companies`,
  `get_company_settings_status`, `create_company_settings` und `get_dtd_status`.
  Dokumentmethoden `get_status`, `list_files` und `verify_package` am Export sowie
  `status` und `overview` an den Unternehmenseinstellungen. `start_export` liefert jetzt
  ein Dict statt eines Strings. Jede Funktion verlangt das Unternehmen ausdrücklich.
- Verstecktes Feld `protocol_json` am Export: das Prüfprotokoll als Daten für die
  Statusabfrage (`Protocol.as_dict()`).
- Knöpfe „Paket prüfen“ und „Unternehmenseinstellungen“ im Export-Formular, Link
  „Unternehmenseinstellungen“ im Arbeitsbereich.
- README-Abschnitte „Mehrere Unternehmen auf einer Instanz“ und „Nutzung durch
  KI-Assistenten (MCP)“.
- Tests: zwei Unternehmen mit eigenen Buchungen und Parteien, deren Exporte nichts
  voneinander enthalten; Benennung in `index.xml`, Prüfprotokoll und LIESMICH;
  Patch-Migration; Geschäftsjahr-Beschränkung; die gesamte Schnittstelle.

### Geändert
- Die Fixtures der Integrationstests sind unabhängig von der Kundennamensvergabe
  (Nummernkreis) und der Standard-Kundengruppe der Site.
- `.gitignore`: veralteter Eintrag für `public/images/logo.svg` entfernt; die Datei ist das
  eingecheckte Schild-Logo seit 0.2.0, kein Fremdartefakt mehr.

## [0.2.2] - 2026-11-26

### Behoben
- Leere `patches.txt` ergänzt. bench erkennt einen App-Ordner nur mit `hooks.py`, `modules.txt`
  und `patches.txt` als Frappe-App (`bench/utils/__init__.py`, `paths_in_app`); ohne die Datei
  fehlte die App beim Image-Bau in `sites/apps.txt`, `bench build` legte keinen Verweis
  `assets/erpnext_gdpdu_export` an, und `/assets/erpnext_gdpdu_export/images/logo.svg` antwortete
  mit 404 (Desk-Kachel ohne Logo). Zur Laufzeit lief die App trotzdem, weil der Container die
  `apps.txt` aus dem Ordnerinhalt neu schreibt.

## [0.2.1] - 2026-11-26

### Hinzugefügt
- Breadcrumb „Alle Apps“ (Link auf `/desk`) vor dem Titel der GDPdU-Export-Einstellungen; Frappe 16
  zeigt für Single-DocTypes sonst nur den Titel ohne Weg zurück zur Desk-Startseite.

## [0.2.0] - 2026-11-26

### Hinzugefügt
- Schild-Logo (`app_logo_url`) und mitgelieferte Desktop-Kachel „GoBD-Export“ für die
  Desk-Startseite von Frappe v16; die Kachel zeigt das Logo statt des Anfangsbuchstabens.

## [0.1.0] - 2026-09-05

### Hinzugefügt
- **Phase 1 — Formatkern:** deklarative Tabellendefinitionen (`gdpdu/schema.py`)
  als einzige Wahrheitsquelle für CSV-Writer und index.xml-Generator;
  Formatierung nach KONZEPT.md §2 (`gdpdu/formats.py`), VariableLength-CSV
  (`gdpdu/csv_writer.py`), index.xml-Erzeugung (`gdpdu/index_xml.py`) sowie
  DTD-Zugriff und -Validierung (`gdpdu/dtd.py`).
- **Phase 2 — Extraktion:** nur lesende Extraktoren für Buchungsjournal
  (chunked über GL Entry), Kontenplan, Debitoren, Kreditoren und
  Steuerkennzeichen; Prüfprotokoll mit Zeilenzahlen, Soll-/Haben-Summen und
  Warnungen in Klartext (`gdpdu/protocol.py`).
- **Phase 3 — Bedienung:** DocTypes *GDPdU Export* und *GDPdU Export Settings*,
  Paketierung als ZIP inkl. `pruefprotokoll.txt` und `LIESMICH.txt`
  (`gdpdu/package.py`), Hintergrund-Job mit Fortschrittsanzeige, Arbeitsbereich
  *GoBD-Export*, deutschsprachige Oberfläche mit Geschäftsjahr-Vorbelegung,
  Statusführung und Download-Knopf.
- Tests: 66 Unit-Tests ohne Site (laufen in der CI mit) und 14 Integrationstests
  gegen eine ERPNext-v15-Site; die erzeugte index.xml wird gegen die
  Original-DTD validiert.

- **Phase 4 — Belegebene:** Ausgangs- und Eingangsrechnungen inkl. Positionen,
  Zahlungen mit Zuordnung zum ausgeglichenen Beleg sowie offene Posten der
  Debitoren und Kreditoren zum Stichtag (aus dem Journal über `against_voucher`
  gerechnet, nicht aus dem tagesaktuellen Saldo). Insgesamt 13 Tabellen.
- **Stufe 3 — Anlagenbuchhaltung:** Anlagenverzeichnis zum Stichtag
  (Anschaffungskosten, Abschreibungsparameter, kumulierte Abschreibung,
  Buchwert, Konten der Anlagenklasse) und Abschreibungszeilen des Zeitraums
  mit Kennzeichen, ob sie bereits gebucht sind. Insgesamt 15 Tabellen.
- Kompatibilität mit **ERPNext/Frappe v15 und v16** aus einer Codebasis, beide
  Versionen vollständig verprobt (siehe KOMPATIBILITAET.md).
- Prüfprotokoll warnt, wenn die Systemzeitzone außerhalb Europas liegt —
  Erfassungszeiten würden sonst verschoben im Export stehen.

### Geändert
- **Lizenz von MIT auf AGPL-3.0** umgestellt — einheitlich mit dem Schwester-Repo
  `qonto_banking` und dem ERPNext-Ökosystem. Betrifft `license.txt`, `hooks.py`,
  `pyproject.toml` und die README.
- Repository nach dem Muster von `qonto_banking` überarbeitet: README mit Badges,
  Entscheidungs- und Troubleshooting-Tabellen, ausführlichem Haftungsabschnitt und
  kommerziellem Support; dazu SECURITY.md, CODE_OF_CONDUCT.md, Issue- und
  PR-Vorlagen, dependabot, `.editorconfig` und `.gitattributes`.
- CI führt die Server-Tests jetzt als Matrix über ERPNext v15 und v16 aus, zusätzlich
  zu Lint und dem Formatkern ohne Site.
- SPEC.md präzisiert: Elementreihenfolge der DTD, Schlüsselspalten zuerst,
  kein ForeignKey auf `Gegenpartei` (dynamisch Debitor/Kreditor), Umgang mit
  doppelten Kontoschlüsseln, Paketinhalt.
- Stufe 2 ist **nicht abwählbar** (Abweichung vom ursprünglichen Konzept mit
  Checkboxen): Den Prüfungsumfang bestimmt die Betriebsprüfung, nicht der
  Steuerpflichtige — Begründung in KONZEPT.md §3.
- Debitoren/Kreditoren enthalten zusätzlich Parteien mit offenem Posten zum
  Stichtag, damit jede Referenz der OPOS-Tabellen auflösbar bleibt.
- CI führt zusätzlich die Unit-Tests des Formatkerns und `ruff format --check` aus.

### Bekannt
- Noch keine Verprobung mit IDEA; steht vor der Freigabe als Version 1.0 an.
- Lohnabrechnungsdaten bleiben außen vor (dafür gibt es die DLS).

## Phase 0

### Hinzugefügt
- Konzept (KONZEPT.md), Maßnahmenplan, SPEC (Feldmapping MVP),
  Arbeitsanweisungen, Frappe-App-Gerüst, CI- und pre-commit-Grundlage.
