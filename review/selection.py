from collections.abc import Sequence

from catalog.lookup import FrozenRowRecord


def validate_interval(start: int, stop: int, row_count: int) -> None:
    if type(start) is not int or type(stop) is not int:
        raise ValueError('review interval endpoints must be integer row positions')
    if not 0 <= start < stop <= row_count:
        raise ValueError(f'review interval must satisfy 0 <= start < stop <= {row_count}')


def bind_selection(
    rows: Sequence[FrozenRowRecord], start: int, stop: int
) -> tuple[FrozenRowRecord, ...]:
    return tuple(rows[start:stop])
