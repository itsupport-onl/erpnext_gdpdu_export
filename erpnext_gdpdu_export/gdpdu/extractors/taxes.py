"""steuerkennzeichen.csv — tax accounts with their rate and usage (SPEC.md).

Convention for the rate (Abnahme ERP-104). ERPNext cannot tell "no rate" from "0 %":
``Account.tax_rate`` is NOT NULL with default 0, and the standard SKR03 templates carry
rows with 0 % for accounts that really have 7 % or 19 %. So 0 never counts as a rate:

1. The rate is the first rate **above 0** from, in this order, the sales tax templates,
   the purchase tax templates and the account itself. An explicit rate above 0 therefore
   wins over a template row with 0 %.
2. A tax account without such a rate that is listed under *Steuerfreie Steuerkonten
   (0 %)* in its company's *GDPdU Company Settings* is exported with 0,00 and no warning:
   that list is the only way to declare a genuine 0 % account.
3. Every other tax account without a rate above 0 is exported with an empty rate and
   produces the protocol warning ``missing_tax_rate``.
"""

from __future__ import annotations

from collections.abc import Iterator

import frappe

from .base import ExtractionContext

TABLE_KEY = "taxes"

SALES = "Sales"
PURCHASE = "Purchase"

_TEMPLATE_RATES = """
	SELECT charge.account_head, MAX(charge.rate) AS rate
	FROM `tab{charge_table}` charge
	INNER JOIN `tab{template_table}` template ON template.name = charge.parent
	WHERE charge.parenttype = %(parenttype)s
		AND template.company = %(company)s
		AND IFNULL(template.disabled, 0) = 0
	GROUP BY charge.account_head
"""


def iter_rows(ctx: ExtractionContext) -> Iterator[dict]:
	sales_rates = _template_rates(ctx, "Sales Taxes and Charges", "Sales Taxes and Charges Template")
	purchase_rates = _template_rates(ctx, "Purchase Taxes and Charges", "Purchase Taxes and Charges Template")
	account_rates = _account_rates(ctx)
	exempt = tax_exempt_accounts(ctx.company)

	for info in ctx.accounts().values():
		if info.account_type != "Tax" or info.is_group:
			continue

		directions = []
		if info.name in sales_rates:
			directions.append(SALES)
		if info.name in purchase_rates:
			directions.append(PURCHASE)

		rate = resolve_rate(
			sales_rates.get(info.name), purchase_rates.get(info.name), account_rates.get(info.name)
		)
		if rate is None and info.name in exempt:
			rate = 0.0

		if rate is None:
			ctx.protocol.add_warning(
				code="missing_tax_rate",
				message="Für mindestens ein Steuerkonto ist kein Steuersatz hinterlegt.",
				hint=(
					"Das Konto wird ohne Satz exportiert. Hinterlegen Sie den Steuersatz (über 0 %) "
					"im Konto oder in einer Steuervorlage. Ist das Konto tatsächlich steuerfrei, "
					"tragen Sie es in den GDPdU Company Settings unter „Steuerfreie Steuerkonten "
					"(0 %)“ ein."
				),
				sample=info.account_name,
			)

		yield {
			"Steuerkonto": info.key,
			"Bezeichnung": info.account_name,
			"Satz": rate,
			"Richtung": "+".join(directions),
		}


def resolve_rate(*candidates: float | None) -> float | None:
	"""The first candidate above 0; 0 and empty values mean "no rate" (see module docstring)."""
	for rate in candidates:
		if rate is not None and rate > 0:
			return rate
	return None


def tax_exempt_accounts(company: str) -> set[str]:
	"""Accounts declared as genuine 0 % accounts in the company's settings record."""
	settings = frappe.db.get_value("GDPdU Company Settings", {"company": company}, "name")
	if not settings:
		return set()
	return set(
		frappe.get_all(
			"GDPdU Tax Exempt Account",
			filters={"parent": settings, "parenttype": "GDPdU Company Settings"},
			pluck="account",
		)
	)


def _template_rates(ctx: ExtractionContext, charge_table: str, template_table: str) -> dict[str, float]:
	query = _TEMPLATE_RATES.format(charge_table=charge_table, template_table=template_table)
	rows = frappe.db.sql(
		query,
		{"company": ctx.company, "parenttype": template_table},
		as_dict=True,
	)
	return {row.account_head: row.rate for row in rows if row.account_head}


def _account_rates(ctx: ExtractionContext) -> dict[str, float]:
	rows = frappe.get_all(
		"Account",
		filters={"company": ctx.company, "account_type": "Tax"},
		fields=["name", "tax_rate"],
	)
	return {row.name: row.tax_rate for row in rows}
