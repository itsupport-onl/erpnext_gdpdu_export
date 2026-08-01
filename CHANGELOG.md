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
