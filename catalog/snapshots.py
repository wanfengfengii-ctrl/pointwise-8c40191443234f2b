from dataclasses import dataclass
from sqlite3 import Connection

from catalog.lookup import (
    FrozenRowRecord,
    RevisionRecord,
    load_revision_record,
    load_revision_rows,
)
from catalog.transactions import Archive, read_snapshot
from intake.source_rows import SourceRef


@dataclass(frozen=True, slots=True)
class FrozenRevision:
    record: RevisionRecord
    rows: tuple[FrozenRowRecord, ...]


@dataclass(frozen=True, slots=True)
class RevisionRow:
    position: int
    source: SourceRef
    value: int | None


@dataclass(frozen=True, slots=True)
class RevisionView:
    revision_id: int
    day_id: str
    batch_id: str
    parent_revision: int | None
    rows: tuple[RevisionRow, ...]


def load_frozen_revision(connection: Connection, revision_id: int) -> FrozenRevision:
    record = load_revision_record(connection, revision_id)
    return FrozenRevision(record, load_revision_rows(connection, record.revision_id))


def read_revision(archive: Archive, revision_id: int) -> RevisionView:
    with read_snapshot(archive) as connection:
        frozen = load_frozen_revision(connection, revision_id)

    record = frozen.record
    return RevisionView(
        record.revision_id,
        record.day_id,
        record.batch_id,
        record.parent_revision,
        tuple(RevisionRow(row.position, row.source, row.value) for row in frozen.rows),
    )
