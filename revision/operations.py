from collections.abc import Sequence

from revision.coordinates import (
    Copy,
    Delete,
    Move,
    Operation,
    move_insert_position,
    validate_insertion_gap,
    validate_row_position,
)
from revision.occurrences import Occurrence


def apply_operations(
    working: list[Occurrence], operations: Sequence[Operation]
) -> None:
    if not isinstance(operations, Sequence) or isinstance(operations, (str, bytes, bytearray)):
        raise ValueError('operations must be an ordered sequence of edit steps')

    for step, operation in enumerate(operations):
        row_count = len(working)
        try:
            if isinstance(operation, Delete):
                validate_row_position(operation.position, row_count)
                del working[operation.position]
            elif isinstance(operation, (Move, Copy)):
                validate_row_position(operation.source, row_count)
                validate_insertion_gap(operation.gap, row_count)
                if isinstance(operation, Move):
                    occurrence = working.pop(operation.source)
                    destination = move_insert_position(operation.source, operation.gap)
                    working.insert(destination, occurrence)
                else:
                    occurrence = Occurrence(working[operation.source].source)
                    working.insert(operation.gap, occurrence)
            else:
                raise ValueError('expected a Move, Copy or Delete')
        except ValueError as error:
            raise ValueError(f'edit step {step}: {error}') from error
