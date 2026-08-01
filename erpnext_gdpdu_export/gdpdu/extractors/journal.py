"""journal.csv — the complete posting journal of the period (SPEC.md).

Source: GL Entry of the company, ``is_cancelled = 0``, ordered by posting date,
creation and name. Rows are fetched in chunks via keyset pagination so a journal
with hundreds of thousands of entries never loads into memory at once.
"""

from __future__ import annotations

from collections.abc import Iterator

import frappe

from ..formats import clean_text
from .base import ExtractionContext

TABLE_KEY = "journal"

_SELECT = """
	SELECT
		gle.name, gle.posting_date, gle.voucher_type, gle.voucher_no, gle.account,
		gle.debit, gle.credit, gle.party_type, gle.party, gle.against, gle.remarks,
		gle.cost_center, gle.creation, gle.owner
	FROM `tabGL Entry` gle
	WHERE gle.company = %(company)s
		AND gle.posting_date BETWEEN %(from_date)s AND %(to_date)s
		AND IFNULL(gle.is_cancelled, 0) = 0
		{cursor}
	ORDER BY gle.posting_date, gle.creation, gle.name
	LIMIT %(limit)s
"""

_CURSOR_CONDITION = """
		AND (gle.posting_date, gle.creation, gle.name) > (%(last_date)s, %(last_creation)s, %(last_name)s)
"""


def iter_rows(ctx: ExtractionContext) -> Iterator[dict]:
	"""Yield one dict per journal line, keyed by the column names of the schema."""
	cursor: tuple | None = None

	while True:
		batch = _fetch(ctx, cursor)
		if not batch:
			return

		for entry in batch:
			yield _to_row(ctx, entry)

		if len(batch) < ctx.chunk_size:
			return

		last = batch[-1]
		cursor = (last.posting_date, last.creation, last.name)


def _fetch(ctx: ExtractionContext, cursor: tuple | None) -> list:
	params = {
		"company": ctx.company,
		"from_date": ctx.from_date,
		"to_date": ctx.to_date,
		"limit": ctx.chunk_size,
	}
	condition = ""
	if cursor:
		condition = _CURSOR_CONDITION
		params.update(
			{
				"last_date": cursor[0],
				"last_creation": cursor[1],
				"last_name": cursor[2],
			}
		)

	return frappe.db.sql(_SELECT.format(cursor=condition), params, as_dict=True)


def _to_row(ctx: ExtractionContext, entry) -> dict:
	account = ctx.accounts().get(entry.account)
	ctx.protocol.add_amounts(entry.debit, entry.credit)

	return {
		"JournalID": entry.name,
		"Buchungsdatum": entry.posting_date,
		# GL Entry carries no separate document date; SPEC.md falls back to the
		# posting date until the document level of stage 2 is exported.
		"Belegdatum": entry.posting_date,
		"Belegart": entry.voucher_type,
		"Belegnummer": entry.voucher_no,
		"Konto": account.key if account else entry.account,
		"Kontobezeichnung": account.account_name if account else entry.account,
		"Soll": entry.debit,
		"Haben": entry.credit,
		"Waehrung": ctx.currency,
		"GegenparteiTyp": entry.party_type,
		"Gegenpartei": entry.party,
		"Gegenkonto": _against_accounts(ctx, entry.against),
		"Buchungstext": clean_text(entry.remarks),
		"Kostenstelle": entry.cost_center,
		"ErfasstAm": entry.creation,
		"ErfasstUm": entry.creation,
		"ErfasstVon": entry.owner,
	}


def _against_accounts(ctx: ExtractionContext, against: str | None) -> str:
	"""Translate the ERPNext ``against`` list into exported account keys."""
	if not against:
		return ""

	keys = []
	for part in str(against).split(","):
		part = part.strip()
		if not part:
			continue
		info = ctx.accounts().get(part)
		keys.append(info.key if info else part)
	return ",".join(keys)
