from collections.abc import Sequence
from dataclasses import dataclass

from review.results import ClaimRow


@dataclass(frozen=True, slots=True)
class HandoffTotals:
    row_count: int
    missing_count: int


def count_totals(rows: Sequence[ClaimRow]) -> HandoffTotals:
    return HandoffTotals(len(rows), sum(row.value is None for row in rows))
