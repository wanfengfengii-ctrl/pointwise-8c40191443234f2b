from dataclasses import dataclass

from delivery.totals import HandoffTotals, count_totals
from review.results import ClaimResult, ClaimRow


@dataclass(frozen=True, slots=True)
class HandoffManifest:
    ticket_id: int
    target_revision: int
    rows: tuple[ClaimRow, ...]
    totals: HandoffTotals


def build_manifest(result: ClaimResult) -> HandoffManifest:
    return HandoffManifest(
        result.ticket_id, result.target_revision, result.rows, count_totals(result.rows)
    )
