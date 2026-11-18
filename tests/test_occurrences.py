import json
import sqlite3

from catalog.snapshots import read_revision
from catalog.transactions import open_archive, read_snapshot
from delivery.export import export
from review.claims import claim
from review.tickets import mark, read_ticket
from revision.coordinates import Copy, Delete, Move
from revision.publish import edit_day, seal_day
from intake.batches import register_batch
from tests.support import ArchiveTestCase, BATCH, claim_lines, freeze, revision_lines


class OccurrenceIdentityTests(ArchiveTestCase):
    def test_paired_withdrawal_selects_distinct_occurrences(self):
        # INCIDENT.md: same-source original and copy must be claimed separately.
        root = freeze(self.archive, [None])
        old_ticket = mark(self.archive, root, 0, 1)
        copied = edit_day(self.archive, root, [Copy(0, 1)])
        original_ticket = mark(self.archive, copied, 0, 1)
        copy_ticket = mark(self.archive, copied, 1, 2)
        delete_original = edit_day(self.archive, copied, [Delete(0)])
        delete_copy = edit_day(self.archive, copied, [Delete(1)])

        reopened = open_archive(self.path)
        self.assertEqual(
            claim_lines(claim(reopened, old_ticket, delete_original)), [])
        self.assertEqual(
            claim_lines(claim(reopened, original_ticket, delete_original)), [])
        self.assertEqual(
            claim_lines(claim(reopened, copy_ticket, delete_original)),
            [[1, 0, BATCH, 0, None]])
        self.assertEqual(
            claim_lines(claim(reopened, old_ticket, delete_copy)),
            [[0, 0, BATCH, 0, None]])
        self.assertEqual(
            claim_lines(claim(reopened, original_ticket, delete_copy)),
            [[0, 0, BATCH, 0, None]])
        self.assertEqual(
            claim_lines(claim(reopened, copy_ticket, delete_copy)), [])

    def test_offline_manifest_matches_claim_detail(self):
        root = freeze(self.archive, [None])
        ticket = mark(self.archive, root, 0, 1)
        copied = edit_day(self.archive, root, [Copy(0, 1)])
        withdrawn = edit_day(self.archive, copied, [Delete(0)])
        surviving = edit_day(self.archive, copied, [Delete(1)])

        for target, expected_rows in ((withdrawn, 0), (surviving, 1)):
            with self.subTest(target=target):
                document = export(self.archive, ticket, target).decode('utf-8')
                payload = json.loads(document)
                self.assertEqual(payload['target_revision'], target)
                self.assertEqual(payload['totals']['row_count'], expected_rows)
                self.assertEqual(payload['totals']['missing_count'], expected_rows)
                self.assertEqual(len(payload['rows']), expected_rows)

    def test_move_keeps_identity_copy_is_independent(self):
        root = freeze(self.archive, [11, 22, None, 44])
        ticket = mark(self.archive, root, 1, 3)
        moved = edit_day(self.archive, root, [Copy(1, 4), Move(1, 0)])
        copy_ticket = mark(self.archive, moved, 4, 5)
        withdrawn = edit_day(self.archive, moved, [Delete(0)])

        self.assertEqual(claim_lines(claim(self.archive, ticket, moved)),
                         [[1, 0, BATCH, 1, 22], [2, 2, BATCH, 2, None]])
        self.assertEqual(claim_lines(claim(self.archive, ticket, withdrawn)),
                         [[2, 1, BATCH, 2, None]])
        self.assertEqual(claim_lines(claim(self.archive, copy_ticket, withdrawn)),
                         [[4, 3, BATCH, 1, 22]])
        self.assertEqual(read_ticket(self.archive, ticket).revision_id, root)

    def test_copies_of_copies_are_separate_occurrences(self):
        root = freeze(self.archive, [7])
        once = edit_day(self.archive, root, [Copy(0, 1)])
        twice = edit_day(self.archive, once, [Copy(1, 2)])
        tickets = [mark(self.archive, twice, index, index + 1) for index in range(3)]
        for index, ticket in enumerate(tickets):
            target = edit_day(self.archive, twice, [Delete(index)])
            lines = claim_lines(claim(self.archive, ticket, target))
            self.assertEqual(lines, [], f'ticket {index} must end when its row is deleted')
            for other in (tickets[:index] + tickets[index + 1:]):
                self.assertEqual(
                    len(claim(self.archive, other, target).rows), 1,
                    'unrelated same-source tickets must still deliver their own row')

    def test_empty_edit_preserves_identities_across_chain(self):
        root = freeze(self.archive, [3, 6])
        ticket = mark(self.archive, root, 0, 2)
        same_order = edit_day(self.archive, root, [])
        moved = edit_day(self.archive, same_order, [Move(1, 0)])
        empty = edit_day(self.archive, moved, [Delete(0), Delete(0)])
        self.assertEqual(
            claim_lines(claim(self.archive, ticket, same_order)),
            [[0, 0, BATCH, 0, 3], [1, 1, BATCH, 1, 6]])
        self.assertEqual(
            claim_lines(claim(self.archive, ticket, moved)),
            [[1, 0, BATCH, 1, 6], [0, 1, BATCH, 0, 3]])
        self.assertEqual(claim(self.archive, ticket, empty).rows, ())
        self.assertEqual(
            revision_lines(read_revision(self.archive, root)),
            [[0, BATCH, 0, 3], [1, BATCH, 1, 6]])

    def test_legacy_archive_migrates_with_distinct_occurrences(self):
        path = self.directory / 'legacy.sqlite3'
        connection = sqlite3.connect(path)
        try:
            connection.execute('PRAGMA foreign_keys = ON')
            connection.executescript(
                '''
                CREATE TABLE source_batches (
                    batch_id TEXT NOT NULL PRIMARY KEY,
                    day_id TEXT NOT NULL,
                    UNIQUE (batch_id, day_id));
                CREATE TABLE source_rows (
                    batch_id TEXT NOT NULL REFERENCES source_batches (batch_id),
                    source_position INTEGER NOT NULL CHECK (source_position >= 0),
                    reading TEXT,
                    PRIMARY KEY (batch_id, source_position)) WITHOUT ROWID;
                CREATE TABLE revisions (
                    revision_id INTEGER PRIMARY KEY,
                    day_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    parent_revision INTEGER,
                    UNIQUE (revision_id, batch_id),
                    CHECK (parent_revision IS NULL OR parent_revision < revision_id),
                    FOREIGN KEY (batch_id, day_id)
                        REFERENCES source_batches (batch_id, day_id),
                    FOREIGN KEY (parent_revision, batch_id)
                        REFERENCES revisions (revision_id, batch_id));
                CREATE TABLE revision_rows (
                    revision_id INTEGER NOT NULL,
                    position INTEGER NOT NULL CHECK (position >= 0),
                    batch_id TEXT NOT NULL,
                    source_position INTEGER NOT NULL,
                    PRIMARY KEY (revision_id, position),
                    FOREIGN KEY (revision_id, batch_id)
                        REFERENCES revisions (revision_id, batch_id),
                    FOREIGN KEY (batch_id, source_position)
                        REFERENCES source_rows (batch_id, source_position))
                    WITHOUT ROWID;
                CREATE TABLE review_tickets (
                    ticket_id INTEGER PRIMARY KEY,
                    revision_id INTEGER NOT NULL REFERENCES revisions (revision_id),
                    start_position INTEGER NOT NULL CHECK (start_position >= 0),
                    stop_position INTEGER NOT NULL CHECK (stop_position > start_position));
                INSERT INTO source_batches VALUES ('track-a', '2026-11-18');
                INSERT INTO source_rows VALUES ('track-a', 0, NULL);
                INSERT INTO revisions VALUES (1, '2026-11-18', 'track-a', NULL);
                INSERT INTO revisions VALUES (2, '2026-11-18', 'track-a', 1);
                INSERT INTO revision_rows VALUES (1, 0, 'track-a', 0);
                INSERT INTO revision_rows VALUES (2, 0, 'track-a', 0);
                INSERT INTO revision_rows VALUES (2, 1, 'track-a', 0);
                INSERT INTO review_tickets VALUES (1, 2, 0, 1);
                INSERT INTO review_tickets VALUES (2, 2, 1, 2);
                '''
            )
            connection.commit()
        finally:
            connection.close()

        archive = open_archive(path)
        self.assertEqual(
            revision_lines(read_revision(archive, 2)),
            [[0, BATCH, 0, None], [1, BATCH, 0, None]])
        with read_snapshot(archive) as db:
            occurrence_ids = [
                row[0] for row in db.execute(
                    'SELECT occurrence_id FROM revision_rows '
                    'WHERE revision_id = 2 ORDER BY position')
            ]
        self.assertEqual(len(occurrence_ids), 2)
        self.assertNotEqual(occurrence_ids[0], occurrence_ids[1])
        delete_first = edit_day(archive, 2, [Delete(0)])
        delete_second = edit_day(archive, 2, [Delete(1)])
        self.assertEqual(claim_lines(claim(archive, 1, delete_first)), [])
        self.assertEqual(claim_lines(claim(archive, 1, delete_second)),
                         [[0, 0, BATCH, 0, None]])
        self.assertEqual(claim_lines(claim(archive, 2, delete_first)),
                         [[1, 0, BATCH, 0, None]])
        self.assertEqual(claim_lines(claim(archive, 2, delete_second)), [])
        # New edits after migration mint ids beyond the backfilled range.
        with read_snapshot(archive) as db:
            copied = edit_day(archive, 2, [Copy(0, 1)])
            new_id = db.execute(
                'SELECT occurrence_id FROM revision_rows '
                'WHERE revision_id = ? AND position = 1', (copied,)).fetchone()[0]
        self.assertGreater(new_id, max(occurrence_ids))
        # Re-opening and retrying a compatible batch keeps the archive usable.
        reopened = open_archive(path)
        self.assertEqual(
            register_batch(reopened, BATCH, '2026-11-18', [None]), BATCH)
        another = seal_day(reopened, '2026-11-18', BATCH)
        self.assertEqual(
            revision_lines(read_revision(reopened, another)), [[0, BATCH, 0, None]])
