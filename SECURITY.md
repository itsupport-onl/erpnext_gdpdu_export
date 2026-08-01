# Sicherheitsrichtlinie

## Schwachstellen melden

Bitte **kein öffentliches Issue** für Sicherheitsprobleme.

Melden Sie privat über GitHubs
[private vulnerability reporting](https://github.com/itsupport-onl/erpnext_gdpdu_export/security/advisories/new)
oder per E-Mail an <tickets@itsupport.onl>.

Bitte angeben: betroffene Version, Beschreibung, Schritte zur Reproduktion und — wenn
möglich — ein Lösungsvorschlag. Sie erhalten innerhalb von 5 Werktagen eine Bestätigung
und mindestens alle 14 Tage eine Statusmeldung, bis das Problem behoben ist.

Geben Sie uns bitte ein angemessenes Zeitfenster für eine Korrektur, bevor Sie
öffentlich darüber berichten.

## Buchhaltungs- und Personendaten gehören nicht in dieses Repository

Die App verarbeitet Buchhaltungsdaten einschließlich personenbezogener Daten von
Kunden, Lieferanten und Mitarbeitern. Folgendes ist nicht verhandelbar:

- **Keine echten Daten in Git.** Keine Kontenpläne aus Produktivsystemen, keine
  Buchungssätze, keine Namen, Anschriften, USt-IdNrn., IBANs oder Benutzerkennungen
  realer Personen — weder im Code noch in Tests, Fixtures, Commit-Nachrichten,
  Issues oder Pull-Request-Beschreibungen. Das gilt auch für private Repositories.
- **Testdaten sind Fantasiedaten.** Die Fixtures verwenden erkennbar erfundene Namen
  (`_Test GDPdU Kundin`, `DE123456789`) und legen ihre eigene Testfirma an.
- **Keine Personendaten in Logs.** Weder in `frappe.log_error`, noch in
  Fehlermeldungen, Tracebacks oder im Prüfprotokoll.
- **Export-Pakete nie anhängen.** Ein erzeugtes ZIP enthält die komplette
  Buchhaltung. Wenn Sie ein Problem zeigen müssen, hängen Sie das Prüfprotokoll oder
  einzelne, anonymisierte Zeilen an — niemals das Paket.

## Wie die App mit Ihren Daten umgeht

- **Nur lesend.** Sie führt ausschließlich SELECTs gegen Buchhaltungsdaten aus und
  schreibt allein in ihre eigenen DocTypes (`GDPdU Export`, `GDPdU Export Settings`).
- **Nichts verlässt Ihr System.** Kein externer Dienst, keine Telemetrie, kein
  Netzwerkzugriff zur Laufzeit.
- **Private Anhänge.** Das Paket wird als privater Dateianhang gespeichert und ist
  nur für Benutzer mit Leserecht am Export-Dokument erreichbar, nicht über einen
  öffentlichen Link.
- **Rechte.** Exporte anlegen und lesen dürfen *System Manager* und
  *Accounts Manager*. Wer diese Rollen vergibt, vergibt Zugriff auf die vollständige
  Buchhaltung inklusive personenbezogener Daten.
- **Aufbewahrung.** Alte Pakete bleiben als Anhang am Export-Dokument liegen, bis Sie
  sie löschen. Wer regelmäßig exportiert, sollte alte Dokumente aufräumen — es sind
  vollständige Kopien Ihrer Buchhaltung.

## Die DTD

`gdpdu-01-08-2002.dtd` ist ein Fremdartefakt der Audicon GmbH. Sie wird von dieser App
niemals verändert, liegt nicht im Repository (`.gitignore` blockiert `*.dtd` unter
`resources/`) und wird byteweise unverändert ins Paket kopiert.

## Unterstützte Versionen

Sicherheitskorrekturen erscheinen für den aktuellen `main`-Stand. Die App wird gegen
ERPNext v15 und v16 getestet.
