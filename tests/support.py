import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from catalog.snapshots import read_revision
from catalog.transactions import open_archive, read_snapshot
from delivery.export import export
from intake.batches import register_batch
from review.claims import claim
from revision.publish import seal_day


DAY = '2026-11-18'
BATCH = 'track-a'


class ArchiveTestCase(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.directory = Path(directory)
        self.path = self.directory / 'track.sqlite3'
        self.archive = open_archive(self.path)


def freeze(archive, values, *, day=DAY, batch=BATCH):
    register_batch(archive, batch, day, values)
    return seal_day(archive, day, batch)


def revision_lines(view):
    return [
        [row.position, row.source.batch_id, row.source.position, row.value]
        for row in view.rows
    ]


def claim_lines(result):
    return [
        [row.marked_position, row.target_position, row.source.batch_id,
         row.source.position, row.value]
        for row in result.rows
    ]


def revision_ids(archive):
    with read_snapshot(archive) as connection:
        rows = connection.execute('SELECT revision_id FROM revisions ORDER BY revision_id')
        return [row[0] for row in rows]


def ticket_ids(archive):
    with read_snapshot(archive) as connection:
        rows = connection.execute('SELECT ticket_id FROM review_tickets ORDER BY ticket_id')
        return [row[0] for row in rows]


def run_reopened(mode, archive_path, *numbers):
    project_root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, '-B', '-m', 'tests.support', mode, str(archive_path),
         *(str(number) for number in numbers)],
        cwd=project_root,
        capture_output=True,
        encoding='utf-8',
        timeout=30,
        check=True,
    )
    return json.loads(completed.stdout)


def _main(args):
    mode, archive_path, first, *rest = args
    archive = open_archive(archive_path)
    if mode == 'revision':
        result = revision_lines(read_revision(archive, int(first)))
    elif mode == 'claims':
        target = int(first)
        result = [claim_lines(claim(archive, int(ticket), target)) for ticket in rest]
    elif mode == 'exports':
        target = int(first)
        result = [export(archive, int(ticket), target).decode('utf-8') for ticket in rest]
    else:
        raise ValueError(f'unknown reopen query {mode!r}')
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    _main(sys.argv[1:])
