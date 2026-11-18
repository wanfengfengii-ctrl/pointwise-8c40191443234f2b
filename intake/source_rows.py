from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceRef:
    batch_id: str
    position: int


@dataclass(frozen=True, slots=True)
class SourceRow:
    source: SourceRef
    value: int | None


def build_source_rows(
    batch_id: str, readings: Iterable[int | None]
) -> tuple[SourceRow, ...]:
    return tuple(
        SourceRow(SourceRef(batch_id, position), value)
        for position, value in enumerate(readings)
    )
