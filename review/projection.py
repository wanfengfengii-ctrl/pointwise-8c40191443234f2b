from collections.abc import Iterable, Sequence

from catalog.lookup import FrozenRowRecord
from review.results import ClaimRow


def project_survivors(
    selected_rows: Sequence[FrozenRowRecord],
    target_rows: Iterable[FrozenRowRecord],
) -> tuple[ClaimRow, ...]:
    # Selections bind to concrete occurrences, not to source references: rows
    # copied from the same source have their own identity and survive or get
    # withdrawn independently. A move keeps the same identity; a delete ends it.
    selected_occurrences = {row.occurrence_id: row.position for row in selected_rows}
    survivors = []
    for target in target_rows:
        marked_position = selected_occurrences.get(target.occurrence_id)
        if marked_position is not None:
            survivors.append(
                ClaimRow(marked_position, target.position, target.source, target.value)
            )
    return tuple(survivors)
