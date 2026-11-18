from dataclasses import dataclass
from sqlite3 import Connection

from intake.format import decode_reading, encode_reading
from intake.source_rows import SourceRef, SourceRow


@dataclass(frozen=True, slots=True)
class StoredBatch:
    batch_id: str
    day_id: str
    rows: tuple[SourceRow, ...]


def load_batch(connection: Connection, batch_id: str) -> StoredBatch | None:
    header = connection.execute(
        'SELECT day_id FROM source_batches WHERE batch_id = ?', (batch_id,)
    ).fetchone()
    if header is None:
        return None

    records = connection.execute(
        '''SELECT source_position, reading
           FROM source_rows WHERE batch_id = ? ORDER BY source_position''',
        (batch_id,),
    )
    rows = tuple(
        SourceRow(SourceRef(batch_id, position), decode_reading(reading))
        for position, reading in records
    )
    return StoredBatch(batch_id, header[0], rows)


def require_batch(connection: Connection, batch_id: str) -> StoredBatch:
    batch = load_batch(connection, batch_id)
    if batch is None:
        raise LookupError(f'unknown source batch {batch_id!r}')
    return batch


def insert_batch(connection: Connection, batch: StoredBatch) -> None:
    connection.execute(
        'INSERT INTO source_batches (batch_id, day_id) VALUES (?, ?)',
        (batch.batch_id, batch.day_id),
    )
    connection.executemany(
        '''INSERT INTO source_rows (batch_id, source_position, reading)
           VALUES (?, ?, ?)''',
        (
            (row.source.batch_id, row.source.position, encode_reading(row.value))
            for row in batch.rows
        ),
    )
