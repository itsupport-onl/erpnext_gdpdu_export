"""Anlagenbuchhaltung: asset register and depreciation lines (SPEC.md, stage 3).

ERPNext renamed the purchase amount field between v15 (``gross_purchase_amount``)
and v16 (``net_purchase_amount``); the field is looked up at runtime so one code
base serves both.
"""

from __future__ import annotations

from collections.abc import Iterator

import frappe

from .base import ExtractionContext, iter_chunks

#: Same meaning, different name per ERPNext version.
PURCHASE_AMOUNT_FIELDS = ("gross_purchase_amount", "net_purchase_amount", "purchase_amount")

_ASSETS = """
	SELECT
		asset.name, asset.asset_name, asset.asset_category, asset.item_code,
		asset.purchase_date, asset.available_for_use_date, asset.{purchase_amount} AS purchase_amount,
		asset.total_asset_cost, asset.asset_quantity, asset.opening_accumulated_depreciation,
		asset.status, asset.disposal_date, asset.cost_center, asset.location,
		asset.creation, asset.owner,
		book.depreciation_method, book.total_number_of_depreciations,
		book.frequency_of_depreciation, book.depreciation_start_date,
		book.expected_value_after_useful_life
	FROM `tabAsset` asset
	LEFT JOIN `tabAsset Finance Book` book
		ON book.parent = asset.name AND book.parenttype = 'Asset' AND book.idx = 1
	WHERE asset.company = %(company)s
		AND asset.docstatus = 1
		AND asset.purchase_date <= %(to_date)s
		AND (asset.disposal_date IS NULL OR asset.disposal_date >= %(from_date)s)
	ORDER BY asset.name
"""

_BOOKED_DEPRECIATION = """
	SELECT schedule.asset AS asset, SUM(line.depreciation_amount) AS booked
	FROM `tabDepreciation Schedule` line
	INNER JOIN `tabAsset Depreciation Schedule` schedule ON schedule.name = line.parent
	WHERE schedule.company = %(company)s
		AND schedule.docstatus = 1
		AND line.schedule_date <= %(to_date)s
		AND IFNULL(line.journal_entry, '') != ''
	GROUP BY schedule.asset
"""

_DEPRECIATIONS = """
	SELECT
		line.name, line.schedule_date, line.depreciation_amount,
		line.accumulated_depreciation_amount, line.journal_entry,
		schedule.asset, schedule.finance_book
	FROM `tabDepreciation Schedule` line
	INNER JOIN `tabAsset Depreciation Schedule` schedule ON schedule.name = line.parent
	WHERE schedule.company = %(company)s
		AND schedule.docstatus = 1
		AND line.schedule_date BETWEEN %(from_date)s AND %(to_date)s
	ORDER BY schedule.asset, line.schedule_date, line.idx
"""

_CATEGORY_ACCOUNTS = """
	SELECT
		account.parent AS asset_category, account.fixed_asset_account,
		account.accumulated_depreciation_account, account.depreciation_expense_account
	FROM `tabAsset Category Account` account
	WHERE account.parenttype = 'Asset Category'
		AND account.company_name = %(company)s
"""


def iter_assets(ctx: ExtractionContext) -> Iterator[dict]:
	accounts = _category_accounts(ctx)
	booked = _booked_depreciation(ctx)
	query = _ASSETS.format(purchase_amount=purchase_amount_field())

	for asset in iter_chunks(query, _params(ctx), ctx.chunk_size):
		category = accounts.get(asset.asset_category, {})
		accumulated = (asset.opening_accumulated_depreciation or 0) + booked.get(asset.name, 0)
		# Additional acquisition costs are part of the book value; on assets
		# without them ERPNext leaves total_asset_cost empty.
		cost = asset.total_asset_cost or asset.purchase_amount or 0

		yield {
			"Anlagennummer": asset.name,
			"Bezeichnung": asset.asset_name,
			"Anlagenklasse": asset.asset_category,
			"Artikel": asset.item_code,
			"Anschaffungsdatum": asset.purchase_date,
			"Inbetriebnahme": asset.available_for_use_date,
			"Anschaffungskosten": asset.purchase_amount,
			"AnschaffungskostenGesamt": cost,
			"Menge": asset.asset_quantity,
			"Abschreibungsmethode": asset.depreciation_method,
			"AnzahlAbschreibungen": asset.total_number_of_depreciations,
			"IntervallMonate": asset.frequency_of_depreciation,
			"Abschreibungsbeginn": asset.depreciation_start_date,
			"Restwert": asset.expected_value_after_useful_life,
			"AbschreibungEroeffnung": asset.opening_accumulated_depreciation,
			"KumulierteAbschreibung": accumulated,
			"BuchwertStichtag": cost - accumulated,
			"Status": asset.status,
			"Abgangsdatum": asset.disposal_date,
			"Kostenstelle": asset.cost_center,
			"Standort": asset.location,
			"Anlagenkonto": ctx.account_key(category.get("fixed_asset_account")),
			"AfAKonto": ctx.account_key(category.get("depreciation_expense_account")),
			"KumAfAKonto": ctx.account_key(category.get("accumulated_depreciation_account")),
			"Stichtag": ctx.to_date,
			"ErfasstAm": asset.creation,
			"ErfasstUm": asset.creation,
			"ErfasstVon": asset.owner,
		}


def iter_depreciations(ctx: ExtractionContext) -> Iterator[dict]:
	for line in iter_chunks(_DEPRECIATIONS, _params(ctx), ctx.chunk_size):
		yield {
			"AbschreibungsID": line.name,
			"Anlagennummer": line.asset,
			"Datum": line.schedule_date,
			"Betrag": line.depreciation_amount,
			"KumulierterBetrag": line.accumulated_depreciation_amount,
			"Belegnummer": line.journal_entry,
			"Gebucht": "1" if line.journal_entry else "0",
			"Finanzbuch": line.finance_book,
		}


def purchase_amount_field() -> str:
	"""Return the field holding the purchase amount in this ERPNext version."""
	meta = frappe.get_meta("Asset")
	for fieldname in PURCHASE_AMOUNT_FIELDS:
		if meta.has_field(fieldname):
			return fieldname

	raise ValueError("Asset doctype has none of the known purchase amount fields")


def _category_accounts(ctx: ExtractionContext) -> dict[str, dict]:
	rows = frappe.db.sql(_CATEGORY_ACCOUNTS, {"company": ctx.company}, as_dict=True)
	return {row.asset_category: row for row in rows}


def _booked_depreciation(ctx: ExtractionContext) -> dict[str, float]:
	rows = frappe.db.sql(
		_BOOKED_DEPRECIATION,
		{"company": ctx.company, "to_date": ctx.to_date},
		as_dict=True,
	)
	return {row.asset: row.booked or 0 for row in rows}


def _params(ctx: ExtractionContext) -> dict:
	return {"company": ctx.company, "from_date": ctx.from_date, "to_date": ctx.to_date}
