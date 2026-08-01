# Mitwirken

Diese App erzeugt Steuerdaten für Betriebsprüfungen. Fehler fallen erst auf,
wenn ein Prüfer vor der Tür steht — deshalb gelten ein paar harte Regeln.

## Harte Regeln

1. **Nur lesend auf Buchhaltungsdaten.** Die App erstellt Exporte. Sie bucht,
   ändert und löscht niemals Buchhaltungsdaten. Kein Code, der GL Entry, Belege
   oder Stammdaten schreibt (Ausnahme: die eigenen DocTypes der App).
2. **SPEC.md ist die Wahrheit.** Änderungen am Feldmapping zuerst in
   [SPEC.md](SPEC.md), dann im Code. index.xml-Generator und CSV-Writer
   konsumieren dieselben Schema-Definitionen aus `gdpdu/schema.py` — niemals
   parallel pflegen.
3. **Keine externen Python-Abhängigkeiten** über das hinaus, was Frappe
   mitbringt (lxml für die DTD-Validierung ist im Frappe-Stack vorhanden).
4. **Die DTD wird nie modifiziert.** `gdpdu-01-08-2002.dtd` ist Fremdartefakt
   (© Audicon), Redistribution-Frage siehe [KONZEPT.md](KONZEPT.md) §7.1. Sie
   gehört nicht ins Repository.
5. **Formatfestlegungen** (KONZEPT.md §2) sind fix: UTF-8, `;`, CRLF,
   VariableLength, YYYYMMDD, Accuracy 2, Kopfzeile mit Range From=2.
   Abweichungen nur nach expliziter Entscheidung der Maintainer.
6. **Personenbezogene Daten** (Debitoren/Kreditoren) niemals in Logs,
   Test-Ausgaben oder Error Logs schreiben; Fixtures verwenden Fantasiedaten.

## Konventionen

- Code und Kommentare Englisch, Nutzer-Dokumentation (README, KONZEPT, SPEC)
  und Oberfläche Deutsch — Zielgruppe sind deutsche Buchhaltungen.
- Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`), pro Thema ein
  Branch, PR gegen `main`.
- Jede neue Funktion mit Test. Extraktoren gegen eigene Fixtures, nicht gegen
  ERPNext-Testdatensätze (siehe [KOMPATIBILITAET.md](KOMPATIBILITAET.md) §2).
- DocType-JSON nur mit `developer_mode 1` exportieren. Wird ein Workspace oder
  DocType geändert, den `modified`-Zeitstempel im JSON anheben — sonst
  übernimmt `bench migrate` die Änderung beim Anwender nicht.
- `CHANGELOG.md` je abgeschlossenem Thema ergänzen.
- `pre-commit install` vor dem ersten Commit; Formatierung per `ruff format`
  (Tabs, wie im Frappe-Ökosystem).

## Tests

Der Formatkern (Schema, CSV-Writer, index.xml, Prüfprotokoll) hat keine
Frappe-Abhängigkeit und läuft ohne Site:

```bash
python -m unittest discover -s erpnext_gdpdu_export/tests -t .
```

Vollständig, inklusive Extraktoren und Paketierung, auf einer Site:

```bash
bench --site <site> run-tests --app erpnext_gdpdu_export
```

Änderungen bitte gegen **ERPNext v15 und v16** prüfen; die bekannten
Unterschiede stehen in [KOMPATIBILITAET.md](KOMPATIBILITAET.md).
