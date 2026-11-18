from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
import sqlite3

from catalog.schema import initialize_schema


@dataclass(frozen=True, slots=True)
class Archive:
    path: Path
    before_commit: Callable[[sqlite3.Connection], None] | None = None


@contextmanager
def _connection(archive: Archive) -> Iterator[sqlite3.Connection]:
    with closing(sqlite3.connect(archive.path, isolation_level=None)) as connection:
        connection.execute('PRAGMA foreign_keys = ON')
        yield connection


@contextmanager
def write_transaction(archive: Archive) -> Iterator[sqlite3.Connection]:
    with _connection(archive) as connection:
        connection.execute('BEGIN IMMEDIATE')
        try:
            yield connection
            if archive.before_commit is not None:
                archive.before_commit(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise


@contextmanager
def read_snapshot(archive: Archive) -> Iterator[sqlite3.Connection]:
    with _connection(archive) as connection:
        connection.execute('PRAGMA query_only = ON')
        connection.execute('BEGIN')
        try:
            yield connection
        finally:
            connection.rollback()


def open_archive(
    path: str | PathLike[str],
    *,
    before_commit: Callable[[sqlite3.Connection], None] | None = None,
) -> Archive:
    """Open a local archive. A diagnostic hook may inspect staged writes before commit."""
    archive_path = Path(path).resolve()
    with write_transaction(Archive(archive_path)) as connection:
        initialize_schema(connection)
    return Archive(archive_path, before_commit)
