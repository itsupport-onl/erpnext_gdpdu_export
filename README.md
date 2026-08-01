# GDPdU/GoBD-Export für ERPNext

> **Status: Konzeptphase / pre-alpha.** Noch kein lauffähiger Export. Konzept in
> [KONZEPT.md](KONZEPT.md), Umsetzungsplan in [MASSNAHMENPLAN.md](MASSNAHMENPLAN.md),
> Feldmapping in [SPEC.md](SPEC.md).

Frappe/ERPNext-App (v15), die die Finanzbuchhaltung als **Datenträgerüberlassung
nach § 147 Abs. 6 AO** exportiert — im Audicon-Beschreibungsstandard (GDPdU/GoBD,
Version 1.6), direkt einlesbar in die Prüfsoftware **IDEA** der Finanzverwaltung.

Ziel: die größte Betriebsprüfungs-Hürde für ERPNext in Deutschland als
Open-Source-Baustein beseitigen, damit mehr deutsche Unternehmen ERPNext für die
Finanzbuchhaltung einsetzen können.

## Was die App nie tun wird

- **Sie bucht nichts.** Nur-Lese-Zugriff auf Journal, Konten und Stammdaten.
- **Sie ändert und löscht nichts** an vorhandenen Buchhaltungsdaten.
- **Sie sendet nichts irgendwohin.** Der Export ist eine private ZIP-Datei in
  deinem ERPNext; die Übergabe an den Prüfer bleibt bei dir.

## Geplanter Umfang (MVP)

Die **gesamte Finanzbuchhaltung** der gewählten Company im gewählten Zeitraum:
vollständiges Buchungsjournal über alle Konten, kompletter Kontenplan,
Debitoren-/Kreditorenstamm und Steuerkennzeichen — ohne inhaltliche Filterung.
Nicht enthalten ist die Lohnabrechnungsebene (dafür existiert die Digitale
LohnSchnittstelle); FiBu-Buchungen zu Personalkosten sind selbstverständlich
Teil des Journals. Belegebene und offene Posten folgen als Stufe 2.

## Haftungsausschluss

Diese Software wird ohne jede Gewährleistung bereitgestellt (MIT-Lizenz,
siehe [license.txt](license.txt)). Sie ersetzt keine steuerliche Beratung und
garantiert keine Anerkennung durch die Finanzverwaltung. Die Verantwortung für
Vollständigkeit und Richtigkeit der übergebenen Daten liegt beim Steuerpflichtigen.
Ein ausführlicher deutscher Haftungsabschnitt folgt vor v1.0
(MASSNAHMENPLAN.md, Phase 5).

## Entwicklung

```bash
bench get-app https://github.com/itsupport-onl/erpnext_gdpdu_export.git
bench --site dev.localhost install-app erpnext_gdpdu_export
bench --site dev.localhost run-tests --app erpnext_gdpdu_export
```

---

Gebaut und gepflegt von **[itsupport.online](https://itsupport.online/)** —
ERPNext-, Netzwerk- und IT-Security-Spezialisten aus Berlin.
© Coozinha UG (haftungsbeschränkt), Berlin, handelnd als itsupport.online, und Contributors.
Impressum: <https://itsupport.online/impressum/>

Nicht verbunden mit Audicon GmbH, Caseware, Frappe Technologies oder der
Finanzverwaltung. „IDEA" ist eine Marke von Caseware International Inc.
