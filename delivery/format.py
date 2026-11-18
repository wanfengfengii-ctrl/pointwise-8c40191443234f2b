from decimal import Decimal
import json

from delivery.manifest import HandoffManifest
from review.results import ClaimRow


def _encode_row(row: ClaimRow) -> str:
    source = json.dumps(
        {'batch_id': row.source.batch_id, 'position': row.source.position},
        ensure_ascii=False,
        separators=(',', ':'),
    )
    # Decimal constructs the exact decimal token even beyond int's digit limit.
    value = 'null' if row.value is None else str(Decimal(row.value))
    return (
        f'{{"marked_position":{row.marked_position},"target_position":{row.target_position},'
        f'"source":{source},"value":{value}}}'
    )


def encode_handoff(manifest: HandoffManifest) -> bytes:
    rows = ','.join(_encode_row(row) for row in manifest.rows)
    totals = json.dumps(
        {'row_count': manifest.totals.row_count, 'missing_count': manifest.totals.missing_count},
        separators=(',', ':'),
    )
    text = (
        f'{{"ticket_id":{manifest.ticket_id},"target_revision":{manifest.target_revision},'
        f'"rows":[{rows}],"totals":{totals}}}\n'
    )
    return text.encode('utf-8')
