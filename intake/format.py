from collections.abc import Iterable, Mapping, Set
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BatchInput:
    batch_id: str
    day_id: str
    readings: tuple[int | None, ...]


def decode_batch(
    batch_id: str, day_id: str, readings: Iterable[int | None]
) -> BatchInput:
    if isinstance(readings, (str, bytes, bytearray, memoryview, Mapping, Set)):
        raise ValueError('readings must be an ordered iterable of readings')
    try:
        materialized = tuple(readings)
    except TypeError as error:
        raise ValueError('readings must be an ordered iterable of readings') from error
    return BatchInput(batch_id, day_id, materialized)


def encode_reading(value: int | None) -> str | None:
    if value is None:
        return None
    return format(value, 'x')


def decode_reading(stored: str | None) -> int | None:
    if stored is None:
        return None
    return int(stored, 16)
