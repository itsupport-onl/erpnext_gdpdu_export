# CLAUDE.md — Arbeitsanweisungen für dieses Repository

## Projekt

Frappe/ERPNext-App (v15) für den GoBD/GDPdU-Export der Finanzbuchhaltung
(Datenträgerüberlassung, Audicon-Beschreibungsstandard 1.6, Zielsoftware IDEA).
Lies vor jeder Arbeit: **KONZEPT.md** (was und warum), **SPEC.md** (verbindliches
Feldmapping), **MASSNAHMENPLAN.md** (aktuelle Phase + DoD).

## Harte Regeln

1. **Nur lesend auf Buchhaltungsdaten.** Diese App erstellt Exporte. Sie bucht,
   ändert und löscht niemals Buchhaltungsdaten. Kein Code, der GL Entry,
   Belege oder Stammdaten schreibt (Ausnahme: eigene DocTypes der App).
2. **SPEC.md ist die Wahrheit.** Feldmapping-Änderungen zuerst in SPEC.md,
   dann im Code. index.xml-Generator und CSV-Writer konsumieren dieselben
   Schema-Definitionen aus `gdpdu/schema.py` — niemals parallel pflegen.
3. **Keine externen Python-Abhängigkeiten** über das hinaus, was Frappe v15
   mitbringt (lxml für DTD-Validierung ist im Frappe-Stack vorhanden).
4. **Die DTD wird nie modifiziert.** `gdpdu-01-08-2002.dtd` ist Fremdartefakt
   (© Audicon), Redistribution-Frage siehe KONZEPT.md §7.1.
5. **Formatfestlegungen** (KONZEPT.md §2) sind fix: UTF-8, `;`, CRLF,
   VariableLength, YYYYMMDD, Accuracy 2, Kopfzeile mit Range From=2.
   Abweichungen nur nach expliziter Entscheidung von Jan.
6. Personenbezogene Daten (Debitoren/Kreditoren) niemals in Logs, Tests-Output
   oder Error Logs schreiben; Fixtures verwenden Fantasiedaten.

## Konventionen (wie qonto_banking)

- Code und Kommentare Englisch, Nutzer-Doku (README, KONZEPT, SPEC) Deutsch
- Conventional Commits; pro Phase ein Branch, PR gegen main
- Tests: `bench --site dev.localhost run-tests --app erpnext_gdpdu_export`;
  jede neue Funktion mit Test, Extraktoren gegen Frappe-Fixtures
- DocType-JSON nur mit `developer_mode 1` exportieren
- pre-commit vor dem ersten Commit installieren
- CHANGELOG.md je abgeschlossener Phase ergänzen

## Definition of Done je Phase

Steht in MASSNAHMENPLAN.md. Eine Phase gilt erst als fertig, wenn ihre DoD
nachweisbar erfüllt ist (Tests grün, im Zweifel Screenshot/Ausgabe in den PR).
