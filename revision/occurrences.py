from collections.abc import Iterable
from dataclasses import dataclass

from catalog.lookup import FrozenRowRecord
from intake.source_rows import SourceRef


@dataclass(frozen=True, slots=True)
class Occurrence:
    source: SourceRef
    occurrence_id: int


def restore_occurrences(rows: Iterable[FrozenRowRecord]) -> list[Occurrence]:
    return [Occurrence(row.source, row.occurrence_id) for row in rows]
