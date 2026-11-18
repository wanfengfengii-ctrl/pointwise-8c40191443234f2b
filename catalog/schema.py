from sqlite3 import Connection


_REGISTRY_TABLE = '''CREATE TABLE IF NOT EXISTS occurrence_registry (
    occurrence_id INTEGER PRIMARY KEY
)'''


_REVISION_ROWS_TABLE = '''CREATE TABLE IF NOT EXISTS revision_rows (
    revision_id INTEGER NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    batch_id TEXT NOT NULL,
    source_position INTEGER NOT NULL,
    occurrence_id INTEGER NOT NULL REFERENCES occurrence_registry (occurrence_id),
    PRIMARY KEY (revision_id, position),
    UNIQUE (revision_id, occurrence_id),
    FOREIGN KEY (revision_id, batch_id) REFERENCES revisions (revision_id, batch_id),
    FOREIGN KEY (batch_id, source_position) REFERENCES source_rows (batch_id, source_position)
) WITHOUT ROWID'''


_TABLES = (
    '''CREATE TABLE IF NOT EXISTS source_batches (
        batch_id TEXT NOT NULL PRIMARY KEY,
        day_id TEXT NOT NULL,
        UNIQUE (batch_id, day_id)
    )''',
    '''CREATE TABLE IF NOT EXISTS source_rows (
        batch_id TEXT NOT NULL REFERENCES source_batches (batch_id),
        source_position INTEGER NOT NULL CHECK (source_position >= 0),
        reading TEXT,
        PRIMARY KEY (batch_id, source_position)
    ) WITHOUT ROWID''',
    '''CREATE TABLE IF NOT EXISTS revisions (
        revision_id INTEGER PRIMARY KEY,
        day_id TEXT NOT NULL,
        batch_id TEXT NOT NULL,
        parent_revision INTEGER,
        UNIQUE (revision_id, batch_id),
        CHECK (parent_revision IS NULL OR parent_revision < revision_id),
        FOREIGN KEY (batch_id, day_id) REFERENCES source_batches (batch_id, day_id),
        FOREIGN KEY (parent_revision, batch_id) REFERENCES revisions (revision_id, batch_id)
    )''',
    _REGISTRY_TABLE,
    '''CREATE TABLE IF NOT EXISTS review_tickets (
        ticket_id INTEGER PRIMARY KEY,
        revision_id INTEGER NOT NULL REFERENCES revisions (revision_id),
        start_position INTEGER NOT NULL CHECK (start_position >= 0),
        stop_position INTEGER NOT NULL CHECK (stop_position > start_position)
    )''',
)


def _table_columns(connection: Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}


def _migrate_legacy_revision_rows(connection: Connection) -> None:
    """Archives frozen before occurrence tracking kept only (batch, source) keys.

    Rebuild the row table with a distinct occurrence id per stored appearance so
    that already-copied rows become independently editable and markable again.
    """
    columns = _table_columns(connection, 'revision_rows')
    if not columns or 'occurrence_id' in columns:
        return
    connection.execute('ALTER TABLE revision_rows RENAME TO revision_rows_legacy')
    connection.execute(_REVISION_ROWS_TABLE)
    legacy_rows = connection.execute(
        '''SELECT revision_id, position, batch_id, source_position
           FROM revision_rows_legacy ORDER BY revision_id, position'''
    ).fetchall()
    for revision_id, position, batch_id, source_position in legacy_rows:
        occurrence_id = connection.execute(
            'INSERT INTO occurrence_registry DEFAULT VALUES'
        ).lastrowid
        connection.execute(
            '''INSERT INTO revision_rows
                   (revision_id, position, batch_id, source_position, occurrence_id)
               VALUES (?, ?, ?, ?, ?)''',
            (revision_id, position, batch_id, source_position, occurrence_id),
        )
    connection.execute('DROP TABLE revision_rows_legacy')


def initialize_schema(connection: Connection) -> None:
    for statement in _TABLES:
        connection.execute(statement)
    _migrate_legacy_revision_rows(connection)
    connection.execute(_REVISION_ROWS_TABLE)
