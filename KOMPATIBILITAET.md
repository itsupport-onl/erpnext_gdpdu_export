# Kompatibilität v15 / v16

Diese App läuft unverändert auf ERPNext/Frappe **v15** und **v16**. Verprobt mit:

| | Frappe | ERPNext | Python | Testlauf |
|---|---|---|---|---|
| v15 | 15.116.1 | 15.118.3 | 3.11 | 94 Tests grün |
| v16 | 16.29.0 | 16.30.0 | 3.14 | 94 Tests grün |

Verprobt wurde jeweils: `install-app`, `migrate`, kompletter Testlauf,
DTD-Validierung der erzeugten `index.xml` sowie ein realer Export im Desk
(Formular, Hintergrund-Job, ZIP-Download, Prüfprotokoll, Arbeitsbereich).

## Unterschiede und wie sie abgefangen sind

### 1. Testbasisklasse

v15 kennt nur `frappe.tests.utils.FrappeTestCase`, v16 zusätzlich (und
bevorzugt) `frappe.tests.IntegrationTestCase`; in v17 fällt die alte Klasse weg.

→ [`erpnext_gdpdu_export/tests/base.py`](erpnext_gdpdu_export/tests/base.py)
wählt zur Importzeit die vorhandene Klasse.

### 2. Automatische Test-Datensätze der verknüpften DocTypes

Beide Versionen erzeugen für Tests im `doctype/`-Ordner automatisch
Test-Datensätze aller verknüpften DocTypes — bei uns Company und Fiscal Year.
Diese Kette zieht ERPNext-Fixtures nach, die sich zwischen den Versionen
unterscheiden: In v16 liegt „Payment Gateway" in der separaten App `payments`,
die Kette bricht deshalb auf einer Site ohne diese App ab.

→ Die Tests legen ihre Stammdaten selbst an und schalten die Automatik ab:
`IGNORE_TEST_RECORD_DEPENDENCIES` (v16) bzw. `test_ignore` (v15) in
[`test_gdpdu_export.py`](erpnext_gdpdu_export/gdpdu_export/doctype/gdpdu_export/test_gdpdu_export.py).

Wichtig zu wissen: `bench run-tests --app <app>` **überspringt in v16 eine
ganze Testkategorie stillschweigend**, wenn deren Vorbereitung fehlschlägt —
der Lauf meldet dann „OK" mit zu wenigen Tests. Zum Gegenprüfen:

```bash
bench --site <site> run-tests --module erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.test_gdpdu_export
```

### 3. Dateiinhalte lesen

`File.get_content()` hat in v15 keinen Parameter und liefert Bytes; in v16 gibt
es `encodings` und je nach Aufruf auch dekodierten Text.

→ [`gdpdu/dtd.py`](erpnext_gdpdu_export/gdpdu/dtd.py) liest die DTD binär vom
Dateipfad und nutzt `get_content()` nur als Rückfallebene. Die DTD bleibt damit
in beiden Versionen bytegleich (CONTRIBUTING.md Regel 4).

### 4. Workspace-Format

v16 ergänzt im DocType „Workspace" die Felder `type` (Pflichtfeld, Default
`Workspace`) und `app`.

→ Beide sind in
[`gobd_export.json`](erpnext_gdpdu_export/gdpdu_export/workspace/gobd_export/gobd_export.json)
gesetzt; v15 ignoriert die unbekannten Schlüssel. `app: erpnext` sorgt dafür,
dass der Arbeitsbereich in v16 dort erscheint, wo die Buchhaltung ohnehin
arbeitet.

### 5. Anlagenbuchhaltung: umbenanntes Feld

Das Feld mit den Anschaffungskosten heißt in v15 `Asset.gross_purchase_amount`
(Label „Net Purchase Amount"), in v16 `Asset.net_purchase_amount` — dasselbe
Feld, nur umbenannt. Ebenso wird eine übernommene Altanlage in v15 über
`is_existing_asset`, in v16 über `asset_type = "Existing Asset"` gekennzeichnet.

→ [`gdpdu/extractors/assets.py`](erpnext_gdpdu_export/gdpdu/extractors/assets.py)
ermittelt das vorhandene Feld zur Laufzeit über `frappe.get_meta`; die
Testdaten nutzen dieselbe Funktion.

## Was gleich geblieben ist

Alle übrigen genutzten Schnittstellen sind in v15 und v16 signaturgleich:
`frappe.enqueue`, `publish_progress`, `publish_realtime`, `Document.db_set`
(inkl. Dict-Form), `log_error`, `get_traceback(with_context=True)`,
`get_cached_value`, `frappe.db.get_single_value` sowie clientseitig
`frappe.db.get_list/get_value/get_single_value`, `frappe.realtime.on`,
`frm.page.set_primary_action` und `frappe.utils.escape_html`.

Ebenso alle gelesenen ERPNext-Felder: GL Entry (`posting_date`, `voucher_type`,
`voucher_no`, `account`, `debit`, `credit`, `party_type`, `party`, `against`,
`remarks`, `cost_center`, `is_cancelled`), Account (`account_number`,
`account_type`, `root_type`, `is_group`, `account_currency`, `tax_rate`),
Customer/Supplier (`tax_id`), Steuervorlagen (`account_head`, `disabled`) und
Company (`default_currency`, `abbr`, `country`).

## Für spätere Versionen im Blick behalten

- v17 entfernt `frappe.tests.utils.FrappeTestCase` — der Shim in `tests/base.py`
  deckt das bereits ab.
- v17 markiert die Kategorisierung von `FrappeTestCase` im Testrunner als
  veraltet; da wir `IntegrationTestCase` bevorzugen, ist das unkritisch.
