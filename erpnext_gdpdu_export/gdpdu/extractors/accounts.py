"""kontenplan.csv — the complete chart of accounts of the company (SPEC.md).

The full chart is exported, not only accounts with movements: that is simpler to
follow for the auditor and keeps the foreign key of the journal resolvable.
"""

from __future__ import annotations

from collections.abc import Iterator

from .base import ExtractionContext

TABLE_KEY = "accounts"


def iter_rows(ctx: ExtractionContext) -> Iterator[dict]:
	for info in ctx.accounts().values():
		yield {
			"Konto": info.key,
			"Kontobezeichnung": info.account_name,
			"Kontotyp": info.account_type,
			"Wurzeltyp": info.root_type,
			"IstGruppe": "1" if info.is_group else "0",
			"Waehrung": info.currency,
		}
