"""steuerkennzeichen.csv — tax accounts with their rate and usage (SPEC.md).

The rate comes from the tax templates of the company; if an account is not used
in any template, the rate stored on the account itself is the fallback.
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

	for info in ctx.accounts().values():
		if info.account_type != "Tax" or info.is_group:
			continue

		directions = []
		if info.name in sales_rates:
			directions.append(SALES)
		if info.name in purchase_rates:
			directions.append(PURCHASE)

		rate = sales_rates.get(info.name)
		if rate is None:
			rate = purchase_rates.get(info.name)
		if rate is None:
			rate = account_rates.get(info.name)

		if rate is None:
			ctx.protocol.add_warning(
				code="missing_tax_rate",
				message="Für mindestens ein Steuerkonto ist kein Steuersatz hinterlegt.",
				hint=(
					"Das Konto wird ohne Satz exportiert. Hinterlegen Sie den Steuersatz im "
					"Konto oder in einer Steuervorlage."
				),
				sample=info.account_name,
			)

		yield {
			"Steuerkonto": info.key,
			"Bezeichnung": info.account_name,
			"Satz": rate,
			"Richtung": "+".join(directions),
		}


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
	return {row.name: row.tax_rate for row in rows if row.tax_rate is not None}
