from intake.format import BatchInput


def validate_identifier(identifier: str, label: str) -> None:
    if type(identifier) is not str or not identifier:
        raise ValueError(f'{label} must be nonempty text')
    try:
        identifier.encode('utf-8')
    except UnicodeEncodeError as error:
        raise ValueError(f'{label} must be valid UTF-8 text') from error


def validate_batch(batch: BatchInput) -> None:
    validate_identifier(batch.batch_id, 'batch id')
    validate_identifier(batch.day_id, 'day id')
    for position, value in enumerate(batch.readings):
        if value is not None and type(value) is not int:
            raise ValueError(f'reading at position {position} must be an integer or None')
