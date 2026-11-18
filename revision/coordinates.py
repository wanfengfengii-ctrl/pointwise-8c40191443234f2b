from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Move:
    source: int
    gap: int


@dataclass(frozen=True, slots=True)
class Copy:
    source: int
    gap: int


@dataclass(frozen=True, slots=True)
class Delete:
    position: int


Operation = Move | Copy | Delete


def validate_row_position(position: int, row_count: int) -> None:
    if type(position) is not int or not 0 <= position < row_count:
        raise ValueError(f'row position must be an integer in [0, {row_count})')


def validate_insertion_gap(gap: int, row_count: int) -> None:
    if type(gap) is not int or not 0 <= gap <= row_count:
        raise ValueError(f'insertion gap must be an integer in [0, {row_count}]')


def move_insert_position(source: int, gap: int) -> int:
    if source < gap:
        return gap - 1
    return gap
