from collections.abc import Iterable
from dataclasses import dataclass
from sqlite3 import Connection

from intake.format import decode_reading
from intake.source_rows import SourceRef


@dataclass(frozen=True, slots=True)
class RevisionRecord:
    revision_id: int
    day_id: str
    batch_id: str
    parent_revision: int | None


@dataclass(frozen=True, slots=True)
class FrozenRowRecord:
    position: int
    source: SourceRef
    value: int | None


def validate_record_id(number: int, label: str) -> None:
    if type(number) is not int or not 0 < number < 2 ** 63:
        raise ValueError(f'{label} must be a positive SQLite integer id')


def load_revision_record(connection: Connection, revision_id: int) -> RevisionRecord:
    validate_record_id(revision_id, 'revision id')
    record = connection.execute(
        '''SELECT revision_id, day_id, batch_id, parent_revision
           FROM revisions WHERE revision_id = ?''',
        (revision_id,),
    ).fetchone()
    if record is None:
        raise LookupError(f'unknown revision {revision_id}')
    return RevisionRecord(*record)


def load_revision_rows(
    connection: Connection, revision_id: int
) -> tuple[FrozenRowRecord, ...]:
    records = connection.execute(
        '''SELECT rows.position, rows.batch_id, rows.source_position, source.reading
           FROM revision_rows AS rows
           JOIN source_rows AS source
             ON source.batch_id = rows.batch_id
            AND source.source_position = rows.source_position
           WHERE rows.revision_id = ?
           ORDER BY rows.position''',
        (revision_id,),
    )
    return tuple(
        FrozenRowRecord(position, SourceRef(batch_id, source_position), decode_reading(reading))
        for position, batch_id, source_position, reading in records
    )


def insert_revision_record(
    connection: Connection, day_id: str, batch_id: str, parent_revision: int | None
) -> RevisionRecord:
    cursor = connection.execute(
        '''INSERT INTO revisions (day_id, batch_id, parent_revision) VALUES (?, ?, ?)''',
        (day_id, batch_id, parent_revision),
    )
    return RevisionRecord(cursor.lastrowid, day_id, batch_id, parent_revision)


def insert_revision_rows(
    connection: Connection, revision_id: int, sources: Iterable[SourceRef]
) -> None:
    connection.executemany(
        '''INSERT INTO revision_rows (revision_id, position, batch_id, source_position)
           VALUES (?, ?, ?, ?)''',
        (
            (revision_id, position, source.batch_id, source.position)
            for position, source in enumerate(sources)
        ),
    )
