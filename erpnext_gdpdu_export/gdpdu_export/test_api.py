"""The whitelisted API: everything the form can do, without the form.

Needs a site. Exercises the module functions of :mod:`erpnext_gdpdu_export.api`
and the document methods they wrap, the same way the REST API and the MCP
server of Frappe 16 call them.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate

from erpnext_gdpdu_export import api
from erpnext_gdpdu_export.gdpdu.index_xml import DTD_FILE_NAME
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings.gdpdu_company_settings import (
	ensure_company_settings,
)
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings.test_gdpdu_company_settings import (
	SUBSIDIARY,
	create_subsidiary_fixtures,
)
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export import run_export
from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.test_gdpdu_export import (
	COMPANY,
	create_fixtures,
)
from erpnext_gdpdu_export.tests.base import AppTestCase


class TestApi(AppTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.year = int(nowdate()[:4])
		cls.from_date = f"{cls.year}-01-01"
		cls.to_date = f"{cls.year}-12-31"
		create_fixtures()
		create_subsidiary_fixtures()
		frappe.db.commit()

	def setUp(self):
		ensure_company_settings(COMPANY)
		ensure_company_settings(SUBSIDIARY)

	def tearDown(self):
		for name in frappe.get_all(
			"GDPdU Export", filters={"company": ("in", [COMPANY, SUBSIDIARY])}, pluck="name"
		):
			frappe.delete_doc("GDPdU Export", name, force=True)
		frappe.db.commit()

	def create(self, company: str = COMPANY, **kwargs) -> dict:
		return api.create_export(company, from_date=self.from_date, to_date=self.to_date, **kwargs)

	def run_job(self, name: str) -> dict:
		run_export(name)
		return api.get_export_status(name)

	# ------------------------------------------------------------------ create

	def test_create_export_returns_the_document_state(self):
		result = self.create()

		self.assertTrue(result["created"])
		self.assertFalse(result["started"])
		self.assertEqual(result["company"], COMPANY)
		self.assertEqual(result["status"], "Entwurf")
		self.assertEqual(result["period_type"], "Benutzerdefiniert")
		self.assertEqual(str(result["from_date"]), self.from_date)
		self.assertEqual(result["files"], [])
		self.assertEqual(result["protocol"], {})

	def test_create_export_needs_a_company_and_a_period(self):
		self.assertRaises(frappe.ValidationError, api.create_export, "", fiscal_year="2026")
		self.assertRaises(frappe.ValidationError, api.create_export, COMPANY)
		self.assertRaises(frappe.ValidationError, api.create_export, "_Test GDPdU Nicht Vorhanden")

	def test_create_and_start_queues_the_job(self):
		with patch("frappe.enqueue") as enqueue:
			result = self.create(start=1)

		self.assertTrue(result["started"])
		self.assertEqual(result["status"], "In Warteschlange")
		self.assertEqual(result["job_name"], f"gdpdu-export-{result['name']}")
		self.assertEqual(enqueue.call_args.kwargs["export_name"], result["name"])

	def test_create_and_start_reports_the_state_after_the_start(self):
		"""ERP-041: the snapshot is taken after queueing, so is_busy matches the status."""
		with patch("frappe.enqueue"):
			result = self.create(start=1)

		self.assertEqual(result["status"], "In Warteschlange")
		self.assertTrue(result["is_busy"])
		self.assertFalse(result["is_finished"])
		status = api.get_export_status(result["name"])
		for key in ("status", "is_busy", "is_finished", "started_at", "finished_at"):
			self.assertEqual(result[key], status[key], key)

	def test_start_export_refuses_a_running_export(self):
		name = self.create()["name"]
		with patch("frappe.enqueue"):
			api.start_export(name)
		self.assertRaises(frappe.ValidationError, api.start_export, name)

	# ------------------------------------------------------------------ status

	def test_status_after_a_run_carries_protocol_files_and_warnings(self):
		name = self.create()["name"]
		status = self.run_job(name)

		self.assertEqual(status["status"], "Fertig")
		self.assertTrue(status["is_finished"])
		self.assertFalse(status["is_busy"])
		self.assertTrue(status["export_file"])
		self.assertEqual(status["download_url"], status["export_file"])
		self.assertEqual(len(status["files"]), 1)
		self.assertTrue(status["files"][0]["is_package"])
		self.assertTrue(status["files"][0]["is_private"])
		self.assertGreater(status["journal_rows"], 0)

		protocol = status["protocol"]
		self.assertEqual(protocol["company"], COMPANY)
		self.assertTrue(protocol["is_balanced"])
		self.assertEqual(protocol["journal_rows"], status["journal_rows"])
		self.assertEqual(status["warnings"], protocol["warnings"])
		self.assertTrue(all({"code", "message", "hint"} <= set(w) for w in status["warnings"]))

	def test_failed_run_is_reported_with_a_message(self):
		name = self.create()["name"]
		with patch(
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export.build_package",
			side_effect=frappe.ValidationError("Testfehler"),
		):
			status = self.run_job(name)

		self.assertEqual(status["status"], "Fehlgeschlagen")
		self.assertEqual(status["error_message"], "Testfehler")
		self.assertEqual(status["files"], [])

	# ---------------------------------------------------------------- package

	def test_verify_package_checks_the_attached_zip(self):
		name = self.create()["name"]
		self.run_job(name)

		result = api.verify_export(name)
		self.assertTrue(result["checked"])
		self.assertEqual(result["missing_files"], [])
		self.assertIn("journal.csv", result["files_in_package"])
		if result["dtd_included"]:
			self.assertTrue(result["ok"], result["problems"])
			self.assertTrue(result["validation_valid"])
		else:
			self.assertFalse(result["ok"])
			self.assertIn(DTD_FILE_NAME, result["message"])

	def test_verify_package_without_a_package(self):
		name = self.create()["name"]
		result = api.verify_export(name)
		self.assertFalse(result["ok"])
		self.assertFalse(result["checked"])

	def test_download_package_streams_the_zip(self):
		name = self.create()["name"]
		status = self.run_job(name)

		api.download_package(name)
		self.assertEqual(frappe.response.filename, status["package_name"])
		self.assertEqual(frappe.response.type, "download")
		self.assertTrue(frappe.response.filecontent.startswith(b"PK"))

	def test_download_package_without_a_package(self):
		name = self.create()["name"]
		self.assertRaises(frappe.ValidationError, api.download_package, name)

	# -------------------------------------------------------------- overview

	def test_overview_is_per_company(self):
		parent = self.create()["name"]
		child = self.create(SUBSIDIARY)["name"]
		self.run_job(child)

		overview = api.company_overview(SUBSIDIARY)
		self.assertEqual(overview["company"], SUBSIDIARY)
		self.assertEqual([row.name for row in overview["exports"]], [child])
		self.assertEqual(overview["latest_completed_export"].name, child)
		self.assertEqual(overview["export_counts"], {"Fertig": 1})
		self.assertEqual(overview["settings"]["company"], SUBSIDIARY)
		self.assertIn("available", overview["dtd"])
		self.assertTrue(any(year["name"] for year in overview["fiscal_years"]))
		self.assertNotIn(parent, [row.name for row in overview["exports"]])

		codes = {problem["code"] for problem in overview["problems"]}
		self.assertNotIn("failed_export", codes)

		parent_overview = api.company_overview(COMPANY)
		self.assertEqual([row.name for row in parent_overview["exports"]], [parent])
		self.assertEqual(parent_overview["export_counts"], {"Entwurf": 1})

	def test_overview_reports_problems(self):
		name = self.create()["name"]
		with patch(
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export.build_package",
			side_effect=frappe.ValidationError("Testfehler"),
		):
			self.run_job(name)

		problems = {p["code"]: p for p in api.company_overview(COMPANY)["problems"]}
		self.assertIn("failed_export", problems)
		self.assertIn("Testfehler", problems["failed_export"]["message"])

	def test_list_exports_filters_by_company_and_status(self):
		self.create()
		child = self.create(SUBSIDIARY)["name"]

		self.assertEqual([row.name for row in api.list_exports(SUBSIDIARY)], [child])
		self.assertEqual(api.list_exports(SUBSIDIARY, status="Fertig"), [])

	def test_list_companies_and_settings(self):
		companies = {row["company"]: row for row in api.list_companies()}
		self.assertIn(COMPANY, companies)
		self.assertIn(SUBSIDIARY, companies)
		self.assertTrue(companies[SUBSIDIARY]["has_settings"])

		status = api.get_company_settings_status(SUBSIDIARY)
		self.assertEqual(status["company"], SUBSIDIARY)

		frappe.delete_doc("GDPdU Company Settings", SUBSIDIARY, force=True)
		created = api.create_company_settings(SUBSIDIARY)
		self.assertEqual(created["name"], SUBSIDIARY)
		self.assertTrue(created["exists"])

	def test_fiscal_years_for_company(self):
		years = api.fiscal_years_for_company(COMPANY)
		self.assertTrue(years)
		self.assertTrue(all({"name", "from_date", "to_date", "closed"} <= set(year) for year in years))

	def test_lookups_need_read_permission_on_exports(self):
		"""ERP-035: fiscal years and export scope only for users who may read exports."""
		from erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_export.gdpdu_export import get_export_scope

		self.assertTrue(get_export_scope())
		frappe.set_user("Guest")
		try:
			self.assertRaises(frappe.PermissionError, api.fiscal_years_for_company, COMPANY)
			self.assertRaises(frappe.PermissionError, get_export_scope)
		finally:
			frappe.set_user("Administrator")

	def test_dtd_status(self):
		status = api.get_dtd_status()
		self.assertEqual(status["file_name"], DTD_FILE_NAME)
		self.assertIn("available", status)

	# --------------------------------------------------------------- cleanup

	def test_delete_old_exports_keeps_the_newest(self):
		names = []
		for _ in range(3):
			name = self.create(SUBSIDIARY)["name"]
			frappe.db.set_value(
				"GDPdU Export",
				name,
				{"status": "Fertig", "finished_at": frappe.utils.now_datetime()},
				update_modified=False,
			)
			names.append(name)
		running = self.create(SUBSIDIARY)["name"]
		frappe.db.set_value("GDPdU Export", running, "status", "Läuft")
		foreign = self.create(COMPANY)["name"]
		frappe.db.set_value("GDPdU Export", foreign, "status", "Fertig")

		preview = api.delete_old_exports(SUBSIDIARY, keep=1, dry_run=1)
		self.assertTrue(preview["dry_run"])
		self.assertEqual(preview["deleted_count"], 2)
		self.assertTrue(frappe.db.exists("GDPdU Export", names[0]))

		result = api.delete_old_exports(SUBSIDIARY, keep=1)
		self.assertEqual(result["deleted_count"], 2)
		self.assertEqual({row["name"] for row in result["deleted"]}, set(names[:2]))
		self.assertTrue(frappe.db.exists("GDPdU Export", names[2]))
		self.assertTrue(frappe.db.exists("GDPdU Export", running))
		self.assertTrue(frappe.db.exists("GDPdU Export", foreign))

	def test_delete_old_exports_by_age_and_company_setting(self):
		old = self.create(SUBSIDIARY)["name"]
		frappe.db.set_value(
			"GDPdU Export",
			old,
			{"status": "Fertig", "finished_at": add_days(nowdate(), -400)},
			update_modified=False,
		)
		recent = self.create(SUBSIDIARY)["name"]
		frappe.db.set_value("GDPdU Export", recent, {"status": "Fertig", "finished_at": nowdate()})

		result = api.delete_old_exports(SUBSIDIARY, older_than_days=365)
		self.assertEqual([row["name"] for row in result["deleted"]], [old])
		self.assertTrue(frappe.db.exists("GDPdU Export", recent))

		# Without arguments the company setting decides; 0 means "do nothing".
		self.assertRaises(frappe.ValidationError, api.delete_old_exports, SUBSIDIARY)
		frappe.db.set_value("GDPdU Company Settings", SUBSIDIARY, "keep_last_exports", 1)
		self.assertEqual(api.delete_old_exports(SUBSIDIARY)["kept"], 1)
		frappe.db.set_value("GDPdU Company Settings", SUBSIDIARY, "keep_last_exports", 0)
