from catalog.ancestry import require_same_or_descendant
from catalog.lookup import validate_record_id
from catalog.snapshots import load_frozen_revision
from catalog.transactions import Archive, read_snapshot
from review.projection import project_survivors
from review.results import ClaimResult
from review.selection import bind_selection
from review.tickets import load_ticket


def claim(archive: Archive, ticket_id: int, target_revision: int) -> ClaimResult:
    validate_record_id(target_revision, 'target revision')
    with read_snapshot(archive) as connection:
        ticket = load_ticket(connection, ticket_id)
        origin = load_frozen_revision(connection, ticket.revision_id)
        same_revision = target_revision == ticket.revision_id
        if same_revision:
            target = origin
        else:
            target = load_frozen_revision(connection, target_revision)
        require_same_or_descendant(connection, ticket.revision_id, target.record)
        selected = bind_selection(origin.rows, ticket.start, ticket.stop)
        return ClaimResult(
            ticket.ticket_id,
            target.record.revision_id,
            project_survivors(selected, target.rows, same_revision=same_revision),
        )
