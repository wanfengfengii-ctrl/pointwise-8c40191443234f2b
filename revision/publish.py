from collections.abc import Sequence
from sqlite3 import Connection

from catalog.lookup import (
    RevisionRecord,
    insert_revision_record,
    insert_revision_rows,
    mint_occurrence_id,
)
from catalog.snapshots import load_frozen_revision
from catalog.transactions import Archive, write_transaction
from intake.validation import validate_identifier
from revision.assemble import assemble_initial_rows, load_initial_batch
from revision.coordinates import Operation
from revision.occurrences import Occurrence, restore_occurrences
from revision.operations import apply_operations


def _freeze_rows(
    connection: Connection, record: RevisionRecord, rows: Sequence[Occurrence]
) -> None:
    insert_revision_rows(
        connection,
        record.revision_id,
        ((row.source, row.occurrence_id) for row in rows),
    )


def seal_day(archive: Archive, day_id: str, batch_id: str) -> int:
    validate_identifier(day_id, 'day id')
    validate_identifier(batch_id, 'batch id')
    with write_transaction(archive) as connection:
        batch = load_initial_batch(connection, day_id, batch_id)
        record = insert_revision_record(connection, day_id, batch_id, None)
        rows = assemble_initial_rows(connection, batch)
        _freeze_rows(connection, record, rows)
    return record.revision_id


def edit_day(
    archive: Archive, parent_revision: int, operations: Sequence[Operation]
) -> int:
    with write_transaction(archive) as connection:
        parent = load_frozen_revision(connection, parent_revision)
        record = insert_revision_record(
            connection, parent.record.day_id, parent.record.batch_id, parent.record.revision_id
        )
        working = restore_occurrences(parent.rows)
        apply_operations(working, operations, lambda: mint_occurrence_id(connection))
        _freeze_rows(connection, record, working)
    return record.revision_id
