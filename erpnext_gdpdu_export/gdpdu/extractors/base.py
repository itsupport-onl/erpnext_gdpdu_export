"""Shared state and helpers for the extractors.

Every extractor is read-only: it runs SELECTs against accounting data and never
writes (CONTRIBUTING.md rule 1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import frappe

from ..protocol import Protocol

#: Rows fetched per database round trip, so large journals never load at once.
DEFAULT_CHUNK_SIZE = 5000


def iter_chunks(query: str, params: dict, chunk_size: int):
	"""Yield rows of ``query`` in chunks; the query must be written without LIMIT."""
	start = 0
	while True:
		batch = frappe.db.sql(
			f"{query} LIMIT {int(chunk_size)} OFFSET {int(start)}",
			params,
			as_dict=True,
		)
		if not batch:
			return

		yield from batch

		if len(batch) < chunk_size:
			return
		start += chunk_size


@dataclass
class AccountInfo:
	"""One account of the chart of accounts, including the exported key."""

	name: str
	key: str
	account_name: str
	account_type: str
	root_type: str
	is_group: int
	currency: str


@dataclass
class ExtractionContext:
	"""Everything the extractors need for one export run."""

	company: str
	from_date: str
	to_date: str
	currency: str
	protocol: Protocol
	chunk_size: int = DEFAULT_CHUNK_SIZE
	#: Shared between extractors, e.g. the open items are needed by two tables.
	cache: dict = field(default_factory=dict, repr=False)
	_accounts: dict[str, AccountInfo] | None = field(default=None, repr=False)

	def accounts(self) -> dict[str, AccountInfo]:
		"""Return all accounts of the company, keyed by ERPNext document name."""
		if self._accounts is None:
			self._accounts = build_account_map(self)
		return self._accounts

	def account_key(self, account_name: str | None) -> str:
		"""Return the exported account key (account number, else account name)."""
		if not account_name:
			return ""
		info = self.accounts().get(account_name)
		return info.key if info else account_name


def build_account_map(ctx: ExtractionContext) -> dict[str, AccountInfo]:
	"""Build the account key map once per export and report ambiguities.

	The key is the account number. Without a number the account name is used —
	the description standard does not prescribe a chart of accounts, but the key
	has to be unique because index.xml declares it as the primary key.
	"""
	rows = frappe.get_all(
		"Account",
		filters={"company": ctx.company},
		fields=[
			"name",
			"account_number",
			"account_name",
			"account_type",
			"root_type",
			"is_group",
			"account_currency",
		],
		order_by="lft asc",
	)

	accounts: dict[str, AccountInfo] = {}
	used_keys: dict[str, str] = {}

	for row in rows:
		number = (row.account_number or "").strip()
		key = number or (row.account_name or "").strip() or row.name

		if not number and not row.is_group:
			ctx.protocol.add_warning(
				code="missing_account_number",
				message="Für mindestens ein Sachkonto ist keine Kontonummer hinterlegt.",
				hint=(
					"Der Export verwendet ersatzweise die Kontobezeichnung. Tragen Sie die "
					"Kontonummer im Konto nach, damit der Prüfer die gewohnte Nummer sieht."
				),
				sample=row.account_name or row.name,
			)

		if key in used_keys:
			# Two accounts would share a primary key: fall back to the unique
			# ERPNext name so the key stays unambiguous for IDEA.
			key = row.name
			ctx.protocol.add_warning(
				code="duplicate_account_key",
				message="Mehrere Konten führen zur selben Kontonummer bzw. Kontobezeichnung.",
				hint=(
					"Der Export verwendet für das doppelte Konto den vollständigen Kontonamen. "
					"Vergeben Sie eindeutige Kontonummern, um Rückfragen zu vermeiden."
				),
				sample=row.account_name or row.name,
			)

		used_keys[key] = row.name
		accounts[row.name] = AccountInfo(
			name=row.name,
			key=key,
			account_name=row.account_name or row.name,
			account_type=row.account_type or "",
			root_type=row.root_type or "",
			is_group=int(row.is_group or 0),
			currency=row.account_currency or ctx.currency,
		)

	return accounts
