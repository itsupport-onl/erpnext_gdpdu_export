// Copyright (c) 2026, itsupport.online and contributors
// For license information, please see license.txt

frappe.ui.form.on("GDPdU Export Settings", {
	refresh(frm) {
		// Frappe 16 draws only the document title for a Single DocType, so the settings page has no
		// way back to the desk home. Put "All Apps" in front of it once per paint.
		const crumbs = frm.page.get_breadcrumbs ? frm.page.get_breadcrumbs() : [];
		if (!crumbs.some((c) => c.href === "/desk")) {
			frm.page.set_breadcrumbs([{ label: __("All Apps"), href: "/desk" }, ...crumbs]);
		}
	},
});
