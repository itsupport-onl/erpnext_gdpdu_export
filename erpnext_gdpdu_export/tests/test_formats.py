"""Format rules of KONZEPT.md section 2. Runs without a Frappe site."""

import datetime
import unittest

from erpnext_gdpdu_export.gdpdu.formats import clean_text, format_date, format_numeric, format_time


class TestFormatDate(unittest.TestCase):
	def test_date_and_datetime(self):
		self.assertEqual(format_date(datetime.date(2024, 1, 31)), "20240131")
		self.assertEqual(format_date(datetime.datetime(2024, 12, 5, 23, 59, 59)), "20241205")

	def test_strings(self):
		self.assertEqual(format_date("2024-01-31"), "20240131")
		self.assertEqual(format_date("2024-01-31 10:12:13"), "20240131")
		self.assertEqual(format_date("20240131"), "20240131")

	def test_empty(self):
		self.assertEqual(format_date(None), "")
		self.assertEqual(format_date(""), "")

	def test_invalid(self):
		with self.assertRaises(ValueError):
			format_date("31.01.2024")


class TestFormatTime(unittest.TestCase):
	def test_values(self):
		self.assertEqual(format_time(datetime.datetime(2024, 1, 31, 8, 5, 9)), "08:05:09")
		self.assertEqual(format_time(datetime.time(23, 59, 59)), "23:59:59")
		self.assertEqual(format_time("2024-01-31 08:05:09.123456"), "08:05:09")
		self.assertEqual(format_time("08:05:09"), "08:05:09")
		self.assertEqual(format_time(datetime.timedelta(hours=8, minutes=5, seconds=9)), "08:05:09")

	def test_empty(self):
		self.assertEqual(format_time(None), "")
		self.assertEqual(format_time(""), "")


class TestFormatNumeric(unittest.TestCase):
	def test_two_decimals_with_comma(self):
		self.assertEqual(format_numeric(1234.5), "1234,50")
		self.assertEqual(format_numeric(0), "0,00")
		self.assertEqual(format_numeric("19"), "19,00")

	def test_no_digit_grouping(self):
		self.assertEqual(format_numeric(1234567.89), "1234567,89")

	def test_negative_sign_is_leading_without_space(self):
		self.assertEqual(format_numeric(-42.5), "-42,50")

	def test_rounding_is_half_up(self):
		self.assertEqual(format_numeric(2.345), "2,35")
		self.assertEqual(format_numeric(2.344), "2,34")

	def test_no_negative_zero(self):
		self.assertEqual(format_numeric(-0.001), "0,00")

	def test_float_noise_does_not_leak(self):
		self.assertEqual(format_numeric(0.1 + 0.2), "0,30")

	def test_empty(self):
		self.assertEqual(format_numeric(None), "")
		self.assertEqual(format_numeric(""), "")


class TestCleanText(unittest.TestCase):
	def test_line_breaks_become_spaces(self):
		self.assertEqual(clean_text("Zeile 1\r\nZeile 2"), "Zeile 1 Zeile 2")
		self.assertEqual(clean_text("Tab\there"), "Tab here")

	def test_umlauts_survive(self):
		self.assertEqual(clean_text("Bürogeräte Müller & Co. ÄÖÜß"), "Bürogeräte Müller & Co. ÄÖÜß")

	def test_empty(self):
		self.assertEqual(clean_text(None), "")
