# GDPdU/GoBD-Export für ERPNext

Frappe/ERPNext-App (v15), die die Finanzbuchhaltung als **Datenträgerüberlassung
nach § 147 Abs. 6 AO** exportiert — im Audicon-Beschreibungsstandard (GDPdU/GoBD,
Version 1.6), bestimmt für die Prüfsoftware **IDEA** der Finanzverwaltung.

Der Prüfer sagt „Bitte die Buchhaltung 2024 auf einem Datenträger" — Sie klicken
im ERPNext auf einen Knopf und erhalten eine ZIP-Datei, die genau das enthält.

> **Status: Vorabversion (0.0.1), noch nicht mit IDEA verprobt.** Format und Beschreibungsdatei
> sind gegen die Original-DTD des Standards validiert und automatisiert getestet;
> eine reale Verprobung durch einen Prüfer oder Steuerberater steht noch aus
> vor der Freigabe als Version 1.0. Rückmeldungen dazu sind
> ausdrücklich erwünscht.

## Kompatibilität

Dieselbe Codebasis läuft auf **ERPNext/Frappe v15 und v16**; beide Versionen sind
mit dem vollständigen Testlauf und einem echten Export im Desk verprobt
(v15: Frappe 15.116 / ERPNext 15.118 · v16: Frappe 16.29 / ERPNext 16.30).

Die vier Stellen, an denen sich die Versionen unterscheiden, sind im Code
abgefangen — Details in [KOMPATIBILITAET.md](KOMPATIBILITAET.md).

## Was die App nie tut

- **Sie bucht nichts.** Nur-Lese-Zugriff auf Journal, Konten und Stammdaten.
- **Sie ändert und löscht nichts** an vorhandenen Buchhaltungsdaten.
- **Sie sendet nichts irgendwohin.** Der Export ist eine private ZIP-Datei in
  Ihrem ERPNext; die Übergabe an den Prüfer bleibt bei Ihnen.

## Installation (einmalig, durch die Administration)

```bash
bench get-app https://github.com/itsupport-onl/erpnext_gdpdu_export.git
bench --site <ihre-site> install-app erpnext_gdpdu_export
```

Danach steht der Arbeitsbereich **GoBD-Export** im Desk zur Verfügung
(Suche: „GDPdU Export"). Zugriff haben die Rollen **System Manager** und
**Accounts Manager**.

### DTD hinterlegen

Der Beschreibungsstandard verlangt, dass die Datei `gdpdu-01-08-2002.dtd` neben
der `index.xml` auf dem Datenträger liegt. Sie gehört der Audicon GmbH und darf
dieser Open-Source-App nicht beigelegt werden. Deshalb einmalig:

1. **GDPdU Export Settings** öffnen
2. Die Datei `gdpdu-01-08-2002.dtd` hochladen (aus dem Beschreibungsstandard der
   Audicon GmbH oder aus einem GoBD-Export einer anderen Buchhaltungssoftware —
   sie ist überall identisch)

Alternativ legt die Administration die Datei nach
`apps/erpnext_gdpdu_export/erpnext_gdpdu_export/resources/`.

Ohne diese Datei läuft der Export weiterhin, das Paket ist dann aber
unvollständig — das Prüfprotokoll weist deutlich darauf hin.

## Export erstellen (für Anwenderinnen und Anwender)

1. Im Desk **GoBD-Export → Exporte → Neu** öffnen
2. **Unternehmen** prüfen (ist vorbelegt) und **Geschäftsjahr** wählen — Von- und
   Bis-Datum werden automatisch gesetzt. Für abweichende Zeiträume „Zeitraum
   festlegen über" auf *Benutzerdefiniert* stellen
3. **Speichern** (Strg+S)
4. **Export erstellen** anklicken und bestätigen. Der Export läuft im Hintergrund;
   Sie können die Seite verlassen. Sie aktualisiert sich selbst, sobald das Paket
   fertig ist
5. **Prüfprotokoll** lesen (siehe unten), dann **Paket herunterladen**

Der Zeitbedarf hängt vom Buchungsvolumen ab: kleine Jahre wenige Sekunden,
große Journale einige Minuten.

## Was im Paket steckt

| Datei | Inhalt |
|---|---|
| `index.xml` | Maschinenlesbare Beschreibung aller Dateien und Spalten für IDEA |
| `gdpdu-01-08-2002.dtd` | Zugehörige DTD (Bestandteil des Standards) |
| `journal.csv` | Vollständiges Buchungsjournal des Zeitraums — die Haupttabelle |
| `kontenplan.csv` | Alle Sachkonten des Unternehmens |
| `debitoren.csv` | Kunden mit Buchungen im Zeitraum oder offenem Posten |
| `kreditoren.csv` | Lieferanten mit Buchungen im Zeitraum oder offenem Posten |
| `steuerkennzeichen.csv` | Steuerkonten mit Steuersatz |
| `ausgangsrechnungen.csv` / `…_positionen.csv` | Ausgangsrechnungen mit Einzelpositionen |
| `eingangsrechnungen.csv` / `…_positionen.csv` | Eingangsrechnungen inkl. Lieferantenbelegnummer |
| `zahlungen.csv` | Zahlungsein- und -ausgänge |
| `zahlungszuordnungen.csv` | welche Zahlung welche Rechnung ausgleicht |
| `opos_debitoren.csv` / `opos_kreditoren.csv` | offene Posten zum Ende des Zeitraums |
| `anlagegueter.csv` | Anlagenverzeichnis mit Anschaffungskosten, Abschreibung und Buchwert |
| `abschreibungen.csv` | Abschreibungen des Zeitraums je Anlage |
| `pruefprotokoll.txt` | Zeilenzahlen, Summen, Hinweise zu diesem Export |
| `LIESMICH.txt` | Klartext-Erläuterung für Anwender und Prüfer |

Exportiert wird die **gesamte Finanzbuchhaltung** des Zeitraums samt Belegebene,
ohne Auswahl einzelner Konten oder Tabellen — genau das erwartet die
Betriebsprüfung. Es gibt bewusst keinen Schalter, um Teile wegzulassen: den
Umfang bestimmt die Prüfung, nicht der Steuerpflichtige. Führt Ihr Betrieb
z. B. keine Rechnungen in ERPNext, bleibt die betreffende Datei einfach leer.
Das genaue Feldmapping steht in [SPEC.md](SPEC.md).

## Das Prüfprotokoll verstehen

Nach jedem Lauf steht im Dokument (und im Paket) ein Protokoll in Klartext:

- **Enthaltene Dateien** mit Anzahl Datensätze — eine Plausibilitätsprüfung auf
  einen Blick
- **Summen Soll/Haben**: müssen übereinstimmen. Weichen sie ab, ist das ein
  Hinweis auf unvollständige Buchungen im Zeitraum — vor der Übergabe klären
- **Hinweise** mit konkreter Handlungsanweisung, z. B.:

| Hinweis | Bedeutung |
|---|---|
| Keine Kontonummer hinterlegt | Der Export nutzt ersatzweise die Kontobezeichnung. Nummern nachtragen, damit der Prüfer die gewohnte Nummer sieht |
| Keine Anschrift beim Geschäftspartner | Adresse im Stammsatz ergänzen |
| Kein Steuersatz am Steuerkonto | Satz im Konto oder in der Steuervorlage hinterlegen |
| `gdpdu-01-08-2002.dtd` fehlt | DTD wie oben beschrieben einmalig hinterlegen |
| Keine Buchungen gefunden | Unternehmen und Zeitraum prüfen |

Zusätzlich meldet das Protokoll, ob die `index.xml` erfolgreich gegen die DTD
geprüft wurde.

## Übergabe an den Prüfer

Das Paket enthält **personenbezogene Daten** (Namen, Anschriften, USt-IdNrn.,
Benutzerkennungen). Es wird deshalb als *privater* Dateianhang gespeichert und
ist nicht über einen offenen Link erreichbar.

Übergeben Sie den Datenträger bzw. die Datei nur verschlüsselt — das empfiehlt
auch die DSAG-Handlungsempfehlung zu GoBD/GDPdU. Verschlüsselung und Transportweg
liegen in Ihrer Verantwortung.

## Nicht enthalten

- **Lohnabrechnungsdaten** — dafür existiert die Digitale LohnSchnittstelle (DLS).
  Alle FiBu-Buchungen zu Personalkosten sind selbstverständlich Teil des Journals
- Kein SKR03/SKR04-Mapping: exportiert werden die Kontonummern und -bezeichnungen
  Ihres ERPNext-Kontenplans 1:1

## Format

UTF-8 ohne BOM · Spaltentrenner `;` · Satztrenner CRLF · Texteinschluss `"`
(im Text verdoppelt) · Dezimaltrenner `,` ohne Tausendertrenner · Datum
`JJJJMMTT` · Beträge mit zwei Nachkommastellen, negatives Vorzeichen
vorangestellt · Kopfzeile vorhanden und in der `index.xml` per `Range From=2`
übersprungen. Begründung und Details: [KONZEPT.md](KONZEPT.md) §2 und
[SPEC.md](SPEC.md).

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
`GDPDU_DTD_PATH=/pfad/zur/gdpdu-01-08-2002.dtd` laufen sie mit.

Hinweis: `bench run-tests` legt ERPNext-Testdaten an und setzt eine Site mit
abgeschlossenem Setup-Assistenten voraus.

## Haftungsausschluss

Diese Software wird ohne jede Gewährleistung bereitgestellt (MIT-Lizenz,
siehe [license.txt](license.txt)). Sie ersetzt keine steuerliche Beratung und
garantiert keine Anerkennung durch die Finanzverwaltung. Die Verantwortung für
Vollständigkeit und Richtigkeit der übergebenen Daten liegt beim
Steuerpflichtigen. Prüfen Sie das Prüfprotokoll vor jeder Übergabe.

---

Gebaut und gepflegt von **[itsupport.online](https://itsupport.online/)** —
ERPNext-, Netzwerk- und IT-Security-Spezialisten aus Berlin.
© Coozinha UG (haftungsbeschränkt), Berlin, handelnd als itsupport.online, und Contributors.
Impressum: <https://itsupport.online/impressum/>

Nicht verbunden mit Audicon GmbH, Caseware, Frappe Technologies oder der
Finanzverwaltung. „IDEA" ist eine Marke von Caseware International Inc.
