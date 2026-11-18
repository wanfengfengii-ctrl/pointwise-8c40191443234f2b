from catalog.snapshots import read_revision
from catalog.transactions import open_archive
from intake.batches import read_batch, register_batch
from review.claims import claim
from review.tickets import mark, read_ticket
from revision.coordinates import Delete, Move
from revision.publish import edit_day, seal_day
from tests.support import (
    ArchiveTestCase, BATCH, DAY, claim_lines, freeze, revision_ids, revision_lines, run_reopened,
)


class IntakeTests(ArchiveTestCase):
    def test_freeze_provenance(self):
        readings = iter([0, None, 7, 7])
        self.assertEqual(register_batch(self.archive, BATCH, DAY, readings), BATCH)
        root = seal_day(self.archive, DAY, BATCH)
        expected = [[0, BATCH, 0, 0], [1, BATCH, 1, None], [2, BATCH, 2, 7], [3, BATCH, 3, 7]]
        self.assertEqual(run_reopened('revision', self.path, root), expected)
        raw = read_batch(self.archive, BATCH)
        self.assertEqual((raw.batch_id, raw.day_id), (BATCH, DAY))
        self.assertEqual([(row.source.position, row.value) for row in raw.rows],
                         [(0, 0), (1, None), (2, 7), (3, 7)])

    def test_initialize_reopen(self):
        root = freeze(self.archive, [0, None, 7, 7])
        child = edit_day(self.archive, root, [Move(3, 0), Delete(2)])
        ticket_id = mark(self.archive, child, 0, 2)

        open_archive(self.path)
        reopened = open_archive(self.path)
        self.assertEqual(register_batch(reopened, BATCH, DAY, [0, None, 7, 7]), BATCH)
        self.assertEqual([row.value for row in read_batch(reopened, BATCH).rows], [0, None, 7, 7])
        original = read_revision(reopened, root)
        self.assertIsNone(original.parent_revision)
        self.assertEqual((original.day_id, original.batch_id), (DAY, BATCH))
        self.assertEqual(revision_lines(original),
                         [[0, BATCH, 0, 0], [1, BATCH, 1, None], [2, BATCH, 2, 7], [3, BATCH, 3, 7]])
        corrected = read_revision(reopened, child)
        self.assertEqual(corrected.parent_revision, root)
        self.assertEqual(revision_lines(corrected), [[0, BATCH, 3, 7], [1, BATCH, 0, 0], [2, BATCH, 2, 7]])
        ticket = read_ticket(reopened, ticket_id)
        self.assertEqual((ticket.ticket_id, ticket.revision_id, ticket.start, ticket.stop),
                         (ticket_id, child, 0, 2))
        self.assertEqual(claim_lines(claim(reopened, ticket_id, child)),
                         [[0, 0, BATCH, 3, 7], [1, 1, BATCH, 0, 0]])
        self.assertEqual(revision_ids(reopened), [root, child])

    def test_invalid_input(self):
        root = freeze(self.archive, [6])
        for invalid in (True, '7', 7.0):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaisesRegex(ValueError, 'position 1'):
                    register_batch(self.archive, 'invalid', DAY, [0, invalid])
                with self.assertRaises(LookupError):
                    read_batch(self.archive, 'invalid')
        with self.assertRaises(ValueError):
            register_batch(self.archive, 'unordered', DAY, {1, 2})
        with self.assertRaises(ValueError):
            register_batch(self.archive, '', DAY, [1])
        with self.assertRaises(LookupError):
            seal_day(self.archive, DAY, 'unknown')
        with self.assertRaisesRegex(ValueError, 'belongs to day'):
            seal_day(self.archive, '2026-11-19', BATCH)
        with self.assertRaises(LookupError):
            read_revision(self.archive, root + 1)
        self.assertEqual(revision_ids(self.archive), [root])
        self.assertEqual(revision_lines(read_revision(self.archive, root)), [[0, BATCH, 0, 6]])

    def test_order_conflict(self):
        values = [0, None, 7, 7]
        self.assertEqual(register_batch(self.archive, BATCH, DAY, values), BATCH)
        self.assertEqual(register_batch(self.archive, BATCH, DAY, tuple(values)), BATCH)
        for day, changed in (
            (DAY, [None, 0, 7, 7]), (DAY, values[:-1]), ('2026-11-19', values)
        ):
            with self.subTest(day=day, readings=changed):
                with self.assertRaisesRegex(ValueError, 'different contents'):
                    register_batch(self.archive, BATCH, day, changed)

        reopened = open_archive(self.path)
        original = read_batch(reopened, BATCH)
        self.assertEqual(original.day_id, DAY)
        self.assertEqual([row.value for row in original.rows], values)
        self.assertEqual([row.source.position for row in original.rows], [0, 1, 2, 3])
