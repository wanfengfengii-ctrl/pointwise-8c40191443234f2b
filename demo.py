import json
from pathlib import Path
from tempfile import TemporaryDirectory

from catalog.transactions import open_archive
from delivery.export import export
from intake.batches import register_batch
from review.claims import claim
from review.tickets import mark
from revision.coordinates import Copy, Delete, Move
from revision.publish import edit_day, seal_day


def _claim_details(result):
    return [
        {'marked_position': row.marked_position, 'target_position': row.target_position,
         'source': {'batch_id': row.source.batch_id, 'position': row.source.position},
         'value': row.value}
        for row in result.rows
    ]


def _expected_row(marked, target, source_position, value):
    return {
        'marked_position': marked,
        'target_position': target,
        'source': {'batch_id': 'track-demo-a', 'position': source_position},
        'value': value,
    }


def main() -> None:
    path = Path(__file__).resolve().parent / 'samples' / 'observations.json'
    sample = json.loads(path.read_text(encoding='utf-8'))
    with TemporaryDirectory() as directory:
        archive_path = Path(directory) / 'demo.sqlite3'
        archive = open_archive(archive_path)
        batch_id = register_batch(archive, sample['batch_id'], sample['day_id'], sample['readings'])
        initial = seal_day(archive, sample['day_id'], batch_id)
        ticket = mark(archive, initial, *sample['selection'])
        moved = edit_day(archive, initial, [Copy(1, 4), Move(1, 0)])
        copy_ticket = mark(archive, moved, 4, 5)
        withdrawn = edit_day(archive, moved, [Delete(0)])

        reopened = open_archive(archive_path)
        requests = {
            'initial': (ticket, initial),
            'moved': (ticket, moved),
            'after_withdrawal': (ticket, withdrawn),
            'copy_ticket_after_withdrawal': (copy_ticket, withdrawn),
        }
        actual = {
            label: _claim_details(claim(reopened, *request)) for label, request in requests.items()
        }
        downstream_actual = {
            label: json.loads(export(reopened, *request)) for label, request in requests.items()
        }

    expected = {
        'initial': [_expected_row(1, 1, 1, 22), _expected_row(2, 2, 2, None)],
        'moved': [_expected_row(1, 0, 1, 22), _expected_row(2, 2, 2, None)],
        'after_withdrawal': [_expected_row(2, 1, 2, None)],
        'copy_ticket_after_withdrawal': [_expected_row(4, 3, 1, 22)],
    }
    expected_counts = {
        'initial': (2, 1),
        'moved': (2, 1),
        'after_withdrawal': (1, 1),
        'copy_ticket_after_withdrawal': (1, 0),
    }
    downstream_expected = {}
    for label, (ticket_id, target_revision) in requests.items():
        row_count, missing_count = expected_counts[label]
        downstream_expected[label] = {
            'ticket_id': ticket_id,
            'target_revision': target_revision,
            'rows': expected[label],
            'totals': {'row_count': row_count, 'missing_count': missing_count},
        }
    if actual != expected or downstream_actual != downstream_expected:
        raise RuntimeError('v6.frozen_survival: claim or manifest disagrees with the hand trace')

    report = {
        'case_id': 'v6.frozen_survival',
        'input': {
            'batch': sample,
            'first_edit': [['copy', 1, 4], ['move', 1, 0]],
            'copy_selection': [4, 5],
            'second_edit': [['delete', 0]],
        },
        'expected': expected,
        'actual': actual,
        'downstream_expected': downstream_expected,
        'downstream_actual': downstream_actual,
        'code_paths': [
            'revision/operations.py', 'revision/publish.py', 'review/claims.py',
            'review/projection.py', 'delivery/export.py',
        ],
        'oracle': '手工区分两条同源 B，逐步列出原选行的目标位置，再单独核算缺测数。',
    }
    print('POINTWISE_SCENARIO ' + json.dumps(report, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    main()
