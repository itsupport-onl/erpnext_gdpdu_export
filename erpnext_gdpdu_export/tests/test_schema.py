"""Schema consistency — the single source of truth for CSV and index.xml."""

import unittest

from erpnext_gdpdu_export.gdpdu import schema


class TestSchema(unittest.TestCase):
	def test_schema_is_consistent(self):
		self.assertEqual(schema.validate_schema(), [])

	def test_all_tables_are_exported_in_spec_order(self):
		self.assertEqual(
			[table.filename for table in schema.get_tables()],
			[
				# Finanzbuchhaltung
				"journal.csv",
				"kontenplan.csv",
				"debitoren.csv",
				"kreditoren.csv",
				"steuerkennzeichen.csv",
				# Belegebene, Zahlungen, offene Posten
				"ausgangsrechnungen.csv",
				"ausgangsrechnungen_positionen.csv",
				"eingangsrechnungen.csv",
				"eingangsrechnungen_positionen.csv",
				"zahlungen.csv",
				"zahlungszuordnungen.csv",
				"opos_debitoren.csv",
				"opos_kreditoren.csv",
				# Anlagenbuchhaltung
				"anlagegueter.csv",
				"abschreibungen.csv",
			],
		)

	def test_scope_is_not_configurable(self):
		# The tax audit defines the scope, not the taxpayer (SPEC.md, stage 2).
		self.assertEqual(schema.get_tables(), schema.ALL_TABLES)
		self.assertEqual(
			schema.ALL_TABLES,
			schema.MVP_TABLES + schema.STAGE_2_TABLES + schema.STAGE_3_TABLES,
		)

	def test_journal_columns_follow_spec(self):
		self.assertEqual(
			schema.JOURNAL.header,
			(
				"JournalID",
				"Buchungsdatum",
				"Belegdatum",
				"Belegart",
				"Belegnummer",
				"Konto",
				"Kontobezeichnung",
				"Soll",
				"Haben",
				"Waehrung",
				"GegenparteiTyp",
				"Gegenpartei",
				"Gegenkonto",
				"Buchungstext",
				"Kostenstelle",
				"ErfasstAm",
				"ErfasstUm",
				"ErfasstVon",
			),
		)

	def test_every_table_has_a_key(self):
		for table in schema.get_tables():
			with self.subTest(table=table.key):
				self.assertGreaterEqual(len(table.key_columns), 1)
				# Key columns are matched positionally by the DTD.
				self.assertEqual(
					table.header[: len(table.key_columns)],
					tuple(column.name for column in table.key_columns),
				)

	def test_open_items_use_a_composite_key(self):
		self.assertEqual(
			[column.name for column in schema.OPEN_ITEMS_CUSTOMERS.key_columns],
			["Partei", "Beleg", "Konto"],
		)

	def test_every_numeric_column_declares_its_accuracy(self):
		for table in schema.get_tables():
			for column in table.columns:
				if column.type == schema.NUMERIC:
					with self.subTest(column=f"{table.key}.{column.name}"):
						self.assertIsNotNone(column.accuracy)
						self.assertGreaterEqual(column.accuracy, 0)

	def test_monetary_columns_use_accuracy_two(self):
		monetary = {
			"Soll",
			"Haben",
			"Satz",
			"Netto",
			"Steuer",
			"Brutto",
			"NettoFirmenwaehrung",
			"SteuerFirmenwaehrung",
			"BruttoFirmenwaehrung",
			"Einzelpreis",
			"Betrag",
			"BetragFirmenwaehrung",
			"ZugeordneterBetrag",
			"OffenerBetrag",
		}
		for table in schema.get_tables():
			for column in table.columns:
				if column.name in monetary:
					with self.subTest(column=f"{table.key}.{column.name}"):
						self.assertEqual(column.type, schema.NUMERIC)
						self.assertEqual(column.accuracy, 2)

	def test_get_table(self):
		self.assertIs(schema.get_table("journal"), schema.JOURNAL)
		with self.assertRaises(KeyError):
			schema.get_table("does-not-exist")

	def test_index_xml_descriptions_stay_ascii(self):
		# Data files are UTF-8; index.xml is kept ASCII so that older IDEA
		# versions cannot stumble over the description texts.
		for table in schema.get_tables():
			with self.subTest(table=table.key):
				table.description.encode("ascii")
				table.name.encode("ascii")
				for column in table.columns:
					column.name.encode("ascii")
					column.description.encode("ascii")
					for value_map in column.maps:
						value_map.to_value.encode("ascii")


class TestSchemaGuards(unittest.TestCase):
	def test_key_columns_must_come_first(self):
		with self.assertRaises(ValueError):
			schema.Table(
				key="broken",
				filename="broken.csv",
				name="Broken",
				description="x",
				columns=(
					schema.Column(name="A", description="x"),
					schema.Column(name="B", is_key=True, description="x"),
				),
			)

	def test_duplicate_columns_are_rejected(self):
		with self.assertRaises(ValueError):
			schema.Table(
				key="broken",
				filename="broken.csv",
				name="Broken",
				description="x",
				columns=(
					schema.Column(name="A", is_key=True, description="x"),
					schema.Column(name="A", description="x"),
				),
			)

	def test_foreign_key_must_reference_own_column(self):
		with self.assertRaises(ValueError):
			schema.Table(
				key="broken",
				filename="broken.csv",
				name="Broken",
				description="x",
				columns=(schema.Column(name="A", is_key=True, description="x"),),
				foreign_keys=(schema.ForeignKey(columns=("B",), references="Kontenplan"),),
			)

	def test_accuracy_only_for_numeric(self):
		with self.assertRaises(ValueError):
			schema.Column(name="A", type=schema.ALPHANUMERIC, accuracy=2)
