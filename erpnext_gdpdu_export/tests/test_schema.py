"""Schema consistency — the single source of truth for CSV and index.xml."""

import unittest

from erpnext_gdpdu_export.gdpdu import schema


class TestSchema(unittest.TestCase):
	def test_schema_is_consistent(self):
		self.assertEqual(schema.validate_schema(), [])

	def test_mvp_tables_are_complete(self):
		self.assertEqual(
			[table.filename for table in schema.get_tables()],
			[
				"journal.csv",
				"kontenplan.csv",
				"debitoren.csv",
				"kreditoren.csv",
				"steuerkennzeichen.csv",
			],
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

	def test_every_table_has_exactly_one_key(self):
		for table in schema.get_tables():
			with self.subTest(table=table.key):
				self.assertEqual(len(table.key_columns), 1)

	def test_amounts_use_accuracy_two(self):
		for table in schema.get_tables():
			for column in table.columns:
				if column.type == schema.NUMERIC:
					with self.subTest(column=f"{table.key}.{column.name}"):
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
