from collections.abc import Iterable

from catalog.transactions import Archive, read_snapshot, write_transaction
from intake.format import decode_batch
from intake.source_rows import build_source_rows
from intake.storage import StoredBatch, insert_batch, load_batch, require_batch
from intake.validation import validate_batch, validate_identifier


def register_batch(
    archive: Archive, batch_id: str, day_id: str, readings: Iterable[int | None]
) -> str:
    batch = decode_batch(batch_id, day_id, readings)
    validate_batch(batch)

    with write_transaction(archive) as connection:
        existing = load_batch(connection, batch.batch_id)
        if existing is None:
            rows = build_source_rows(batch.batch_id, batch.readings)
            insert_batch(connection, StoredBatch(batch.batch_id, batch.day_id, rows))
        else:
            existing_readings = tuple(row.value for row in existing.rows)
            if existing.day_id != batch.day_id or existing_readings != batch.readings:
                raise ValueError(f'batch {batch.batch_id!r} already has different contents')

    return batch.batch_id


def read_batch(archive: Archive, batch_id: str) -> StoredBatch:
    validate_identifier(batch_id, 'batch id')
    with read_snapshot(archive) as connection:
        return require_batch(connection, batch_id)
