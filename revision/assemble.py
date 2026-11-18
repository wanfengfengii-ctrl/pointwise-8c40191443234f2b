from sqlite3 import Connection

from catalog.lookup import mint_occurrence_id
from intake.storage import StoredBatch, require_batch
from revision.occurrences import Occurrence


def load_initial_batch(connection: Connection, day_id: str, batch_id: str) -> StoredBatch:
    batch = require_batch(connection, batch_id)
    if batch.day_id != day_id:
        raise ValueError(f'batch {batch_id!r} belongs to day {batch.day_id!r}')
    return batch


def assemble_initial_rows(connection: Connection, batch: StoredBatch) -> list[Occurrence]:
    return [
        Occurrence(row.source, mint_occurrence_id(connection)) for row in batch.rows
    ]
