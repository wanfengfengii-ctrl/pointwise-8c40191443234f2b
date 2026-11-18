from dataclasses import dataclass

from intake.source_rows import SourceRef


@dataclass(frozen=True, slots=True)
class ClaimRow:
    marked_position: int
    target_position: int
    source: SourceRef
    value: int | None


@dataclass(frozen=True, slots=True)
class ClaimResult:
    ticket_id: int
    target_revision: int
    rows: tuple[ClaimRow, ...]
