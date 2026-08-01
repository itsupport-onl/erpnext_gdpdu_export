# Changelog

## [Unreleased]

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

### Geändert
- SPEC.md präzisiert: Elementreihenfolge der DTD, Schlüsselspalten zuerst,
  kein ForeignKey auf `Gegenpartei` (dynamisch Debitor/Kreditor), Umgang mit
  doppelten Kontoschlüsseln, Paketinhalt.
- CI führt zusätzlich die Unit-Tests des Formatkerns und `ruff format --check` aus.

### Bekannt
- Noch keine Verprobung mit IDEA (Phase 5).
- Stufe 2 (Belegebene, offene Posten) und Anlagenbuchhaltung fehlen.

## Phase 0

### Hinzugefügt
- Konzept (KONZEPT.md), Maßnahmenplan, SPEC (Feldmapping MVP),
  CLAUDE.md, Frappe-App-Gerüst, CI- und pre-commit-Grundlage.
