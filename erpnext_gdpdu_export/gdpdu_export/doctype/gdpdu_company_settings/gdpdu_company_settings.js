// Form script of the per-company settings: tax-exempt account filter and a shortcut to the
// exports of this company.

frappe.ui.form.on("GDPdU Company Settings", {
	setup(frm) {
		// Only tax accounts of this company can be declared tax-exempt (0 %).
		frm.set_query("tax_exempt_accounts", () => ({
			filters: { company: frm.doc.company, account_type: "Tax", is_group: 0 },
		}));
	},
	refresh(frm) {
		if (frm.is_new()) {
			return;
		}
		frm.add_custom_button(__("Exporte dieses Unternehmens"), () => {
			frappe.set_route("List", "GDPdU Export", { company: frm.doc.company });
		});
	},
});
