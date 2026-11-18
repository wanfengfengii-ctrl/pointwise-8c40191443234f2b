from sqlite3 import Connection

from catalog.lookup import RevisionRecord, load_revision_record


def require_same_or_descendant(
    connection: Connection, marked_revision: int, target: RevisionRecord
) -> None:
    current = target
    while current.revision_id != marked_revision:
        if current.parent_revision is None or current.revision_id < marked_revision:
            raise ValueError(
                f'revision {target.revision_id} is outside the lineage of '
                f'marked revision {marked_revision}'
            )
        current = load_revision_record(connection, current.parent_revision)
