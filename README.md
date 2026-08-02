# GoBD/GDPdU-Export für ERPNext

[![CI](https://github.com/itsupport-onl/erpnext_gdpdu_export/actions/workflows/ci.yml/badge.svg)](https://github.com/itsupport-onl/erpnext_gdpdu_export/actions/workflows/ci.yml)
[![License: AGPL v3](https://img.shields.io/badge/license-AGPL--3.0-blue.svg)](license.txt)
[![ERPNext v15 | v16](https://img.shields.io/badge/ERPNext-v15%20%7C%20v16-0089ff.svg)](https://erpnext.com)
[![Commercial support](https://img.shields.io/badge/commercial%20support-itsupport.online-1f883d.svg)](https://itsupport.online/)

Der Prüfer verlangt die Buchhaltung „auf einem Datenträger" — Sie wählen Unternehmen
und Geschäftsjahr, klicken auf einen Knopf und haben sie: eine ZIP-Datei im
**Audicon-Beschreibungsstandard 1.6**, die die Prüfsoftware **IDEA** der
Finanzverwaltung einliest. Datenträgerüberlassung nach § 147 Abs. 6 AO (Z3-Zugriff).

Gebaut und gepflegt von **[itsupport.online](https://itsupport.online/)** —
ERPNext-, Netzwerk- und IT-Security-Spezialisten aus Berlin. Dauerhaft kostenlos;
[kommerziellen Support](#kommerzieller-support) gibt es, wenn jemand anderes das
übernehmen soll.

> **Status: Vorabversion (0.0.1), noch nicht mit IDEA verprobt.** Format und
> Beschreibungsdatei sind gegen die Original-DTD des Standards validiert, 94 Tests
> laufen auf ERPNext v15 und v16. Was aussteht, ist die Verprobung durch einen Prüfer
> oder Steuerberater. Lesen Sie [Gewährleistung und Haftung](#gewährleistung-und-haftung),
> bevor Sie sich darauf verlassen — und geben Sie das erste Paket vorab Ihrem
> Steuerberater zur Sicht.

## Was sich für Sie ändert

Heute bedeutet eine Prüferanfrage: Auswertungen exportieren, Tabellen zusammenstellen,
Formate erklären, nachliefern. Mit dieser App entsteht in wenigen Minuten ein Paket,
das die Finanzverwaltung in ihrer eigenen Software öffnen kann — mitsamt einer
maschinenlesbaren Beschreibung jeder Spalte, damit keine Rückfrage zum Format entsteht.

Was danach passiert, bleibt unverändert: Sie prüfen das Ergebnis und übergeben es.

## Was die App nie tun wird

Das ist die wichtigere Hälfte, denn darauf sollen Sie vertrauen.

- **Sie bucht nichts.** Nur-Lese-Zugriff auf Journal, Belege und Stammdaten. Kein
  Code der App schreibt in Ihre Buchhaltung.
- **Sie ändert und löscht nichts** an vorhandenen Daten — auch keine Belege, keine
  Konten, keine Festschreibung.
- **Sie sendet nichts irgendwohin.** Das Paket ist ein privater Dateianhang in Ihrem
  ERPNext. Kein Cloud-Dienst, keine Telemetrie. Die Übergabe an den Prüfer bleibt bei Ihnen.
- **Sie entscheidet nicht über den Umfang.** Exportiert wird, was die Prüfung erwartet —
  nicht eine Auswahl, die im Nachhinein als unvollständig gelten könnte.

## Was Sie vor dem ersten Export entscheiden

Vier Dinge, die Ihnen die Software nicht abnehmen kann.

| Entscheidung | Warum sie zählt |
|---|---|
| **Welches Unternehmen** exportiert wird | Bei mehreren Mandanten in einer Instanz wird je Unternehmen ein eigenes Paket erstellt. Der Prüfungsauftrag nennt das Unternehmen |
| **Welcher Zeitraum** | In der Regel das geprüfte Geschäftsjahr. Die App schlägt das letzte abgeschlossene vor; abweichende Zeiträume sind frei wählbar |
| **Wer Exporte erstellen darf** | Das Paket enthält personenbezogene Daten. Zugriff haben *System Manager* und *Accounts Manager* |
| **Wie Sie übergeben** | Verschlüsselter Datenträger oder verschlüsselter Transportweg — siehe [Übergabe an den Prüfer](#übergabe-an-den-prüfer) |

## Einrichtung

Einmalig, durch die Administration:

```bash
bench get-app https://github.com/itsupport-onl/erpnext_gdpdu_export.git
bench --site <ihre-site> install-app erpnext_gdpdu_export
```

Danach steht der Arbeitsbereich **GoBD-Export** im Desk bereit (Suche: „GDPdU Export").

### DTD hinterlegen

Der Beschreibungsstandard verlangt, dass die Datei `gdpdu-01-08-2002.dtd` neben der
`index.xml` auf dem Datenträger liegt. Sie gehört der Audicon GmbH und darf dieser
Open-Source-App nicht beigelegt werden. Deshalb einmalig:

1. **GDPdU Export Settings** öffnen
2. `gdpdu-01-08-2002.dtd` hochladen — aus dem Beschreibungsstandard der Audicon GmbH
   oder aus einem GoBD-Export einer anderen Buchhaltungssoftware; sie ist überall identisch

Alternativ legt die Administration die Datei nach
`apps/erpnext_gdpdu_export/erpnext_gdpdu_export/resources/`.

Ohne diese Datei läuft der Export weiter, das Paket ist dann aber unvollständig — das
Prüfprotokoll weist deutlich darauf hin.

## Export erstellen

1. **GoBD-Export → Meine Exporte → Neu**
2. **Unternehmen** prüfen (ist vorbelegt) und **Geschäftsjahr** wählen — Von- und
   Bis-Datum werden automatisch gesetzt. Für abweichende Zeiträume auf
   *Benutzerdefiniert* stellen
3. **Speichern** (Strg+S)
4. **Export erstellen** anklicken und bestätigen. Der Export läuft im Hintergrund;
   Sie können die Seite verlassen, sie aktualisiert sich selbst
5. **Prüfprotokoll** lesen, dann **Paket herunterladen**

Der Zeitbedarf hängt vom Buchungsvolumen ab: kleine Jahre wenige Sekunden, große
Journale einige Minuten.

## Was im Paket steckt

| Datei | Inhalt |
|---|---|
| `index.xml` | Maschinenlesbare Beschreibung aller Dateien und Spalten für IDEA |
| `gdpdu-01-08-2002.dtd` | Zugehörige DTD (Bestandteil des Standards) |
| `journal.csv` | Vollständiges Buchungsjournal des Zeitraums — die Haupttabelle |
| `kontenplan.csv` | Alle Sachkonten des Unternehmens |
| `debitoren.csv` · `kreditoren.csv` | Kunden und Lieferanten mit Buchung im Zeitraum oder offenem Posten |
| `steuerkennzeichen.csv` | Steuerkonten mit Steuersatz |
| `ausgangsrechnungen.csv` · `…_positionen.csv` | Ausgangsrechnungen mit Einzelpositionen |
| `eingangsrechnungen.csv` · `…_positionen.csv` | Eingangsrechnungen inkl. Lieferantenbelegnummer |
| `zahlungen.csv` · `zahlungszuordnungen.csv` | Zahlungen und welche Rechnung sie ausgleichen |
| `opos_debitoren.csv` · `opos_kreditoren.csv` | Offene Posten zum Ende des Zeitraums |
| `anlagegueter.csv` | Anlagenverzeichnis mit Anschaffungskosten, Abschreibung und Buchwert |
| `abschreibungen.csv` | Abschreibungen des Zeitraums je Anlage |
| `pruefprotokoll.txt` | Zeilenzahlen, Summen und Hinweise zu diesem Export |
| `LIESMICH.txt` | Klartext-Erläuterung für Anwender und Prüfer |

Exportiert wird die **gesamte Finanzbuchhaltung** des Zeitraums samt Belegebene und
Anlagenbuchhaltung — ohne Auswahl einzelner Konten oder Tabellen. Es gibt bewusst
keinen Schalter, um Teile wegzulassen: Den Umfang bestimmt die Prüfung, nicht der
Steuerpflichtige (GoBD Rz. 159). Führt Ihr Betrieb etwa keine Anlagen in ERPNext,
bleibt die betreffende Datei einfach leer.

Welche Spalte woher kommt, steht vollständig in [SPEC.md](SPEC.md).

## Das Prüfprotokoll verstehen

Nach jedem Lauf steht im Dokument und im Paket ein Protokoll in Klartext: enthaltene
Dateien mit Datensatzzahlen, die Summen Soll und Haben — die übereinstimmen müssen —
und Hinweise mit konkreter Handlungsanweisung.

| Hinweis | Bedeutung |
|---|---|
| Keine Kontonummer hinterlegt | Der Export nutzt ersatzweise die Kontobezeichnung. Nummern nachtragen, damit der Prüfer die gewohnte Nummer sieht |
| Soll und Haben weichen ab | Hinweis auf unvollständige Buchungen im Zeitraum. Vor der Übergabe mit der Buchhaltung klären |
| Keine Anschrift beim Geschäftspartner | Adresse im Stammsatz ergänzen |
| Kein Steuersatz am Steuerkonto | Satz im Konto oder in der Steuervorlage hinterlegen |
| `gdpdu-01-08-2002.dtd` fehlt | DTD wie oben beschrieben einmalig hinterlegen |
| Systemzeitzone außerhalb Europas | Erfassungszeiten werden in dieser Zeitzone exportiert; für eine deutsche Prüfung ist `Europe/Berlin` zu erwarten |
| Keine Buchungen gefunden | Unternehmen und Zeitraum prüfen |

Zusätzlich meldet das Protokoll, ob die `index.xml` erfolgreich gegen die DTD geprüft wurde.

## Wenn etwas nicht stimmt

| Was Sie sehen | Was es bedeutet |
|---|---|
| Status bleibt auf *In Warteschlange* | Der Hintergrunddienst läuft nicht. Administration: `bench doctor`, Queue `long` prüfen |
| Status *Fehlgeschlagen* mit Meldung im Dokument | Die Meldung nennt die Ursache im Klartext; technische Details stehen im **Fehlerprotokoll (Error Log)** |
| Kein Knopf „Export erstellen" | Das Dokument ist noch nicht gespeichert oder hat ungespeicherte Änderungen |
| Paket lässt sich nicht herunterladen | Der Dateianhang ist privat; Sie brauchen Leserechte auf das Export-Dokument |
| IDEA meldet ein Formatproblem | Prüfen, ob `index.xml` **und** DTD im selben Verzeichnis liegen. Das Protokoll sagt, ob die DTD im Paket war |
| Zahlen wirken zu niedrig | Stornierte Buchungen sind bewusst nicht enthalten, ebenso Belege im Entwurfsstatus — sie sind buchhalterisch nicht existent |

Das Protokoll enthält keine personenbezogenen Daten. Hängen Sie dennoch nichts an ein
öffentliches Issue an, ohne es vorher durchzusehen.

## Übergabe an den Prüfer

Das Paket enthält **personenbezogene Daten**: Namen, Anschriften, USt-IdNrn. und die
Benutzerkennungen Ihrer Mitarbeiter. Es wird deshalb als *privater* Dateianhang
gespeichert und ist nicht über einen offenen Link erreichbar.

Übergeben Sie es nur verschlüsselt — auf einem verschlüsselten Datenträger oder über
einen verschlüsselten Transportweg. Verschlüsselung und Transportweg liegen in Ihrer
Verantwortung. Der Prüfer darf die Daten nur für die Prüfung verwenden und muss sie
nach deren Abschluss löschen (§ 147 Abs. 6 Satz 3 AO).

## Nicht enthalten

- **Lohnabrechnungsdaten** — dafür existiert die Digitale LohnSchnittstelle (DLS).
  Alle FiBu-Buchungen zu Personalkosten sind selbstverständlich Teil des Journals
- **Belegbilder/Scans** — die Datenträgerüberlassung umfasst die strukturierten Daten;
  Belegbilder werden üblicherweise separat bereitgestellt
- Kein SKR03/SKR04-Mapping: exportiert werden die Kontonummern und -bezeichnungen
  Ihres ERPNext-Kontenplans 1:1

## Format

UTF-8 ohne BOM · Spaltentrenner `;` · Satztrenner CRLF · Texteinschluss `"` (im Text
verdoppelt) · Dezimaltrenner `,` ohne Tausendertrenner · Datum `JJJJMMTT` · Beträge mit
zwei Nachkommastellen, negatives Vorzeichen vorangestellt · Kopfzeile vorhanden und in
der `index.xml` per `Range From=2` übersprungen.

Begründung und Details: [KONZEPT.md](KONZEPT.md) §2 und [SPEC.md](SPEC.md).

## Kompatibilität

Dieselbe Codebasis läuft auf **ERPNext/Frappe v15 und v16**; beide sind mit dem
vollständigen Testlauf und einem echten Export im Desk verprobt. Die vier Stellen, an
denen sich die Versionen unterscheiden, stehen in [KOMPATIBILITAET.md](KOMPATIBILITAET.md).

## Roadmap

| Stufe | Inhalt |
|---|---|
| 1 | Finanzbuchhaltung: Journal, Kontenplan, Stammdaten, Steuerkennzeichen — **fertig** |
| 2 | Belegebene: Rechnungen mit Positionen, Zahlungen, offene Posten — **fertig** |
| 3 | Anlagenbuchhaltung: Anlagenverzeichnis und Abschreibungen — **fertig** |
| 4 | Verprobung mit IDEA durch Prüfer oder Steuerberater, danach Release 0.1.0 |
| 5 | Rückmeldungen aus der Praxis einarbeiten |

Vorerst außerhalb des Umfangs: Lohndaten (DLS), SKR-Mapping, Belegbilder, Z1-/Z2-Zugriff,
DATEV-Export, Verfahrensdokumentation.

## Entwicklung

```bash
bench --site <ihre-site> run-tests --app erpnext_gdpdu_export
```

Der Formatkern (Schema, CSV-Writer, index.xml, Prüfprotokoll) hat keine
Frappe-Abhängigkeit und läuft auch ohne Site:

```bash
python -m unittest discover -s erpnext_gdpdu_export/tests -t .
```

Die DTD-Validierungstests werden übersprungen, solange keine DTD vorliegt; mit
`GDPDU_DTD_PATH=/pfad/zur/gdpdu-01-08-2002.dtd` laufen sie mit. Regeln und
Konventionen: [CONTRIBUTING.md](CONTRIBUTING.md).

## Kommerzieller Support

Diese App ist freie Software und bleibt es — installieren, betreiben, forken, ohne
Gegenleistung. Fehlerberichte und Pull Requests werden hier im Repository bearbeitet,
kostenfrei.

Wenn Sie das nicht selbst betreiben möchten, können es die Leute tun, die es gebaut
haben. **[itsupport.online](https://itsupport.online/)** ist ein IT-Dienstleister aus
Berlin für ERPNext, Netzwerke und IT-Security:

| Leistung | Was das heißt |
|---|---|
| **Einrichtung & Einweisung** | Installation, DTD-Hinterlegung, Rechte, Probelauf mit Ihren Daten |
| **Betrieb & Hosting** | Gemanagtes ERPNext, Updates, Sicherungen, Überwachung |
| **Prüfungsbegleitung** | Paket erstellen, Plausibilitäten klären, Rückfragen des Prüfers beantworten |
| **Anpassungen** | Zusätzliche Tabellen und Felder, Anbindung an Ihre Vorsysteme |

**Kontakt:** [itsupport.online](https://itsupport.online/) ·
<tickets@itsupport.onl> · +49 (0)30 2359 0378 1

## Lizenz

[AGPL-3.0](license.txt) — © Coozinha UG (haftungsbeschränkt), Berlin, handelnd als
[itsupport.online](https://itsupport.online/).

Impressum: <https://itsupport.online/impressum/>

## Gewährleistung und Haftung

Dieses Programm ist freie Software: Sie können es unter den Bedingungen der GNU Affero
General Public License, Version 3 oder (nach Ihrer Wahl) einer späteren Version,
weitergeben und/oder verändern.

Die Veröffentlichung erfolgt in der Hoffnung, dass es nützlich ist, jedoch **OHNE JEDE
GEWÄHRLEISTUNG** — sogar ohne die implizite Gewährleistung der **MARKTREIFE** oder der
**VERWENDBARKEIT FÜR EINEN BESTIMMTEN ZWECK**. Die vollständige Haftungsfreistellung
steht in den Abschnitten 15 und 16 von [license.txt](license.txt).

### Was das in der Praxis heißt

Diese App liest steuerlich relevante Daten aus und stellt sie einer Behörde zur
Verfügung. Sie schreibt nichts in Ihre Buchhaltung. Trotzdem:

- **Prüfen Sie jedes Paket vor der Übergabe.** Das Prüfprotokoll ist dafür gemacht:
  Datensatzzahlen, Soll-gleich-Haben und die Hinweise. Maßgeblich ist Ihre
  Buchhaltung, nicht das, was diese App daraus erzeugt hat.
- **Vollständigkeit und Richtigkeit der übergebenen Daten verantwortet der
  Steuerpflichtige** — daran ändert kein Werkzeug etwas.
- **Keine Anerkennungsgarantie.** Ob die Finanzverwaltung ein Paket im Einzelfall
  akzeptiert, hängt vom Prüfungsauftrag und vom Prüfer ab. Diese App erzeugt ein Format;
  sie kann keine Zusage über dessen Annahme machen.
- **Das ist keine Steuerberatung.** Welche Daten in Ihrem Fall vorzulegen sind, klären
  Sie mit Ihrem Steuerberater oder der Prüfungsanordnung.
- **Erst auf einer Kopie testen.** Führen Sie den ersten Export auf einer Testinstanz
  oder einer Sicherung aus und lassen Sie das Ergebnis vorab prüfen.

Die Nutzung ist Ihre Entscheidung und Ihr Risiko. Wer Teile dieses Risikos vertraglich
abgeben möchte: dafür gibt es [kommerziellen Support](#kommerzieller-support).

## Marken

Dieses Projekt steht in keiner Verbindung zur Audicon GmbH, zu Caseware, zu Frappe
Technologies oder zur Finanzverwaltung und wird von diesen weder unterstützt noch
gesponsert. „IDEA" ist eine Marke von Caseware International Inc., „ERPNext" und
„Frappe" sind Marken von Frappe Technologies. Sie werden hier nur genannt, um zu
beschreiben, womit diese Software zusammenarbeitet.
