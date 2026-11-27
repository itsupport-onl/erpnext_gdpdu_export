"""Every export and every settings record names its company explicitly.

Frappe fills an empty ``company`` field of a new document from the user's or the global
default company before any hook of the document runs. For an audit export that default
would be a silent guess: a REST or MCP client that forgets the company would get a
package of whichever company happens to be the default. The README promises that the
interface always asks for the company, so the guess is undone here and the document
refuses to save without one.
"""

from __future__ import annotations

import frappe


class ExplicitCompanyMixin:
	def _set_defaults(self):
		explicit = self.get("company") if self.is_new() else None
		super()._set_defaults()
		if self.is_new() and not explicit and not frappe.flags.in_import:
			self.company = None

	def require_company(self) -> None:
		if not self.get("company"):
			frappe.throw(
				"Bitte geben Sie das Unternehmen ausdrücklich an. Das Standardunternehmen wird hier "
				"nicht angenommen.",
				frappe.MandatoryError,
				title="Unternehmen fehlt",
			)
