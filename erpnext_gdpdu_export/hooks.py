import frappe

app_name = "erpnext_gdpdu_export"
app_title = "GDPdU Export"
app_publisher = "itsupport.online"
app_description = (
	"GoBD/GDPdU export (Datentraegerueberlassung, Audicon Beschreibungsstandard 1.6) "
	"for ERPNext accounting data, importable by the IDEA audit software."
)
app_email = "tickets@itsupport.onl"
app_license = "agpl-3.0"
# Shown on the desk home, in the app switcher and wherever Frappe needs a mark for the app
app_logo_url = "/assets/erpnext_gdpdu_export/images/logo.svg"
required_apps = ["erpnext"]

# Entry on the apps screen (/apps; Frappe 16: the standard start page "Apps"). Frappe 16
# serves the desk under /desk and only redirects /app, so the route follows the version.
_DESK_PREFIX = "/desk" if int(frappe.__version__.split(".")[0]) >= 16 else "/app"
add_to_apps_screen = [
	{
		"name": app_name,
		"logo": app_logo_url,
		"title": app_title,
		"route": f"{_DESK_PREFIX}/gobd-export",
		"has_permission": "erpnext_gdpdu_export.api.has_app_permission",
	}
]

# Every company created after the installation gets its GDPdU Company Settings record
# right away (companies that already existed are covered by the patch of 0.3.0).
doc_events = {
	"Company": {
		"after_insert": (
			"erpnext_gdpdu_export.gdpdu_export.doctype.gdpdu_company_settings."
			"gdpdu_company_settings.create_for_new_company"
		),
	},
}
