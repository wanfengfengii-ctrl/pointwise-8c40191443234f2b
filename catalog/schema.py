from sqlite3 import Connection


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
    '''CREATE TABLE IF NOT EXISTS revision_rows (
        revision_id INTEGER NOT NULL,
        position INTEGER NOT NULL CHECK (position >= 0),
        batch_id TEXT NOT NULL,
        source_position INTEGER NOT NULL,
        PRIMARY KEY (revision_id, position),
        FOREIGN KEY (revision_id, batch_id) REFERENCES revisions (revision_id, batch_id),
        FOREIGN KEY (batch_id, source_position) REFERENCES source_rows (batch_id, source_position)
    ) WITHOUT ROWID''',
    '''CREATE TABLE IF NOT EXISTS review_tickets (
        ticket_id INTEGER PRIMARY KEY,
        revision_id INTEGER NOT NULL REFERENCES revisions (revision_id),
        start_position INTEGER NOT NULL CHECK (start_position >= 0),
        stop_position INTEGER NOT NULL CHECK (stop_position > start_position)
    )''',
)


def initialize_schema(connection: Connection) -> None:
    for statement in _TABLES:
        connection.execute(statement)
