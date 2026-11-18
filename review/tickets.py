from dataclasses import dataclass
from sqlite3 import Connection

from catalog.lookup import validate_record_id
from catalog.snapshots import load_frozen_revision
from catalog.transactions import Archive, read_snapshot, write_transaction
from review.selection import validate_interval


@dataclass(frozen=True, slots=True)
class ReviewTicket:
    ticket_id: int
    revision_id: int
    start: int
    stop: int


def mark(archive: Archive, revision_id: int, start: int, stop: int) -> int:
    with write_transaction(archive) as connection:
        snapshot = load_frozen_revision(connection, revision_id)
        validate_interval(start, stop, len(snapshot.rows))
        cursor = connection.execute(
            '''INSERT INTO review_tickets (revision_id, start_position, stop_position)
               VALUES (?, ?, ?)''',
            (snapshot.record.revision_id, start, stop),
        )
        ticket_id = cursor.lastrowid
    return ticket_id


def load_ticket(connection: Connection, ticket_id: int) -> ReviewTicket:
    validate_record_id(ticket_id, 'ticket id')
    record = connection.execute(
        '''SELECT ticket_id, revision_id, start_position, stop_position
           FROM review_tickets WHERE ticket_id = ?''',
        (ticket_id,),
    ).fetchone()
    if record is None:
        raise LookupError(f'unknown review ticket {ticket_id}')
    return ReviewTicket(*record)


def read_ticket(archive: Archive, ticket_id: int) -> ReviewTicket:
    with read_snapshot(archive) as connection:
        return load_ticket(connection, ticket_id)
