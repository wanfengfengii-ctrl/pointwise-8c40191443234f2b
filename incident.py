import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from catalog.snapshots import read_revision
from catalog.transactions import open_archive
from delivery.export import export
from intake.batches import register_batch
from review.claims import claim
from review.tickets import mark
from revision.coordinates import Copy, Delete
from revision.publish import edit_day, seal_day


def claim_rows(result):
    return [
        {
            'marked_position': row.marked_position,
            'target_position': row.target_position,
            'source': {'batch_id': row.source.batch_id, 'position': row.source.position},
            'value': row.value,
        }
        for row in result.rows
    ]


def run_case(path):
    archive = open_archive(path)
    batch = register_batch(archive, 'shift-a', '2026-11-18', [None])
    root = seal_day(archive, '2026-11-18', batch)
    old = mark(archive, root, 0, 1)
    copied = edit_day(archive, root, [Copy(0, 1)])
    original = mark(archive, copied, 0, 1)
    duplicate = mark(archive, copied, 1, 2)
    targets = (edit_day(archive, copied, [Delete(0)]), edit_day(archive, copied, [Delete(1)]))

    reopened = open_archive(path)
    expected = {}
    actual = {}
    for label, target, survivors in (
        ('delete_original', targets[0], (None, None, 1)),
        ('delete_copy', targets[1], (0, 0, None)),
    ):
        rows = read_revision(reopened, target).rows
        if [(row.position, row.source.batch_id, row.source.position, row.value) for row in rows] != [
            (0, batch, 0, None)
        ]:
            raise AssertionError('the target day table should retain one row from the original batch')

        expected[label] = []
        actual[label] = []
        for ticket, marked_position in zip((old, original, duplicate), survivors, strict=True):
            wanted = []
            if marked_position is not None:
                wanted.append({
                    'marked_position': marked_position,
                    'target_position': 0,
                    'source': {'batch_id': batch, 'position': 0},
                    'value': None,
                })
            expected[label].append({
                'claim_rows': wanted,
                'export': {
                    'ticket_id': ticket,
                    'target_revision': target,
                    'rows': wanted,
                    'totals': {'row_count': len(wanted), 'missing_count': len(wanted)},
                },
            })
            actual[label].append({
                'claim_rows': claim_rows(claim(reopened, ticket, target)),
                'export': json.loads(export(reopened, ticket, target)),
            })
    return expected, actual


def main() -> int:
    with TemporaryDirectory() as directory:
        expected, actual = run_case(Path(directory) / 'observations.sqlite3')
    print(json.dumps({'expected': expected, 'actual': actual}, ensure_ascii=False, sort_keys=True))
    if actual != expected:
        print('OBS_LAKE_REVIEW_OCCURRENCE_MISMATCH', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
