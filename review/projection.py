from collections.abc import Iterable, Sequence

from catalog.lookup import FrozenRowRecord
from review.results import ClaimRow


def project_survivors(
    selected_rows: Sequence[FrozenRowRecord],
    target_rows: Iterable[FrozenRowRecord],
    *,
    same_revision: bool,
) -> tuple[ClaimRow, ...]:
    if same_revision:
        return tuple(
            ClaimRow(row.position, row.position, row.source, row.value)
            for row in selected_rows
        )

    selected_positions = {
        (row.source.batch_id, row.source.position): row.position for row in selected_rows
    }
    survivors = []
    for target in target_rows:
        source_key = (target.source.batch_id, target.source.position)
        marked_position = selected_positions.get(source_key)
        if marked_position is not None:
            survivors.append(
                ClaimRow(marked_position, target.position, target.source, target.value)
            )
    return tuple(survivors)
