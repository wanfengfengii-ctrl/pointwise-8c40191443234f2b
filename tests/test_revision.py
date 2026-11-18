from catalog.snapshots import read_revision
from catalog.transactions import open_archive
from review.claims import claim
from review.tickets import mark, read_ticket
from revision.coordinates import Copy, Delete, Move
from revision.publish import edit_day
from tests.support import (
    ArchiveTestCase, BATCH, claim_lines, freeze, revision_ids, revision_lines, ticket_ids,
)


class CommitInterrupted(RuntimeError):
    pass


class RevisionTests(ArchiveTestCase):
    def test_move_gap(self):
        root = freeze(self.archive, [10, 20, 30, 40])
        ticket_id = mark(self.archive, root, 1, 3)
        corrected = edit_day(self.archive, root, [Copy(1, 4), Move(0, 3)])
        ordered = read_revision(self.archive, corrected)
        self.assertEqual(ordered.parent_revision, root)
        self.assertEqual(revision_lines(ordered),
                         [[0, BATCH, 1, 20], [1, BATCH, 2, 30], [2, BATCH, 0, 10],
                          [3, BATCH, 3, 40], [4, BATCH, 1, 20]])
        self.assertEqual(revision_lines(read_revision(self.archive, root)),
                         [[0, BATCH, 0, 10], [1, BATCH, 1, 20], [2, BATCH, 2, 30], [3, BATCH, 3, 40]])
        ticket = read_ticket(self.archive, ticket_id)
        self.assertEqual((ticket.revision_id, ticket.start, ticket.stop), (root, 1, 3))
        self.assertEqual(claim_lines(claim(self.archive, ticket_id, root)),
                         [[1, 1, BATCH, 1, 20], [2, 2, BATCH, 2, 30]])

    def test_mark_bounds(self):
        root = freeze(self.archive, [10, 20, 30, 40])
        copied = edit_day(self.archive, root, [Copy(1, 4)])
        original_id = mark(self.archive, copied, 1, 2)
        copy_id = mark(self.archive, copied, 4, 5)
        self.assertNotEqual(original_id, copy_id)
        self.assertEqual(claim_lines(claim(self.archive, original_id, copied)), [[1, 1, BATCH, 1, 20]])
        self.assertEqual(claim_lines(claim(self.archive, copy_id, copied)), [[4, 4, BATCH, 1, 20]])
        for start, stop in ((-1, 1), (0, 0), (3, 2), (5, 6), (1, 6), (False, 2), (0, 2.0)):
            with self.subTest(start=start, stop=stop):
                with self.assertRaises(ValueError):
                    mark(self.archive, copied, start, stop)
        with self.assertRaises(LookupError):
            mark(self.archive, copied + 1, 0, 1)
        self.assertEqual(ticket_ids(self.archive), [original_id, copy_id])

    def test_invalid_suffix(self):
        root = freeze(self.archive, [10, 20, 30, 40])
        ticket = mark(self.archive, root, 1, 2)
        with self.assertRaisesRegex(ValueError, 'edit step 1.*row position'):
            edit_day(self.archive, root, [Move(1, 0), Delete(4)])

        reopened = open_archive(self.path)
        self.assertEqual(revision_ids(reopened), [root])
        with self.assertRaises(LookupError):
            read_revision(reopened, root + 1)
        self.assertEqual(revision_lines(read_revision(reopened, root)),
                         [[0, BATCH, 0, 10], [1, BATCH, 1, 20], [2, BATCH, 2, 30], [3, BATCH, 3, 40]])
        self.assertEqual(ticket_ids(reopened), [ticket])
        self.assertEqual(claim_lines(claim(reopened, ticket, root)), [[1, 1, BATCH, 1, 20]])

    def test_empty_revision_and_edit_bounds(self):
        root = freeze(self.archive, [9])
        for invalid in (Move(0, 2), Copy(0, -1), Delete(False), Copy(-1, 0), 'move'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    edit_day(self.archive, root, [invalid])
        self.assertEqual(revision_ids(self.archive), [root])
        ticket = mark(self.archive, root, 0, 1)
        same_order = edit_day(self.archive, root, [Move(0, 0), Move(0, 1)])
        self.assertEqual(claim_lines(claim(self.archive, ticket, same_order)), [[0, 0, BATCH, 0, 9]])
        empty = edit_day(self.archive, same_order, [Delete(0)])
        empty_child = edit_day(self.archive, empty, [])
        self.assertEqual(read_revision(self.archive, empty_child).rows, ())
        self.assertEqual(claim(self.archive, ticket, empty_child).rows, ())
        with self.assertRaises(ValueError):
            mark(self.archive, empty, 0, 1)

    def test_reopen_retry(self):
        root = freeze(self.archive, [10, 20, 30, 40])
        ticket = mark(self.archive, root, 1, 3)
        operations = [Copy(1, 4), Move(1, 0)]
        staged = []

        def interrupt(connection):
            candidates = connection.execute(
                'SELECT revision_id, parent_revision FROM revisions WHERE parent_revision = ?',
                (root,),
            ).fetchall()
            self.assertEqual(len(candidates), 1)
            revision_id, parent = candidates[0]
            self.assertEqual(parent, root)
            candidate_rows = connection.execute(
                '''SELECT position, source_position FROM revision_rows
                   WHERE revision_id = ? ORDER BY position''',
                (revision_id,),
            ).fetchall()
            self.assertEqual(candidate_rows, [(0, 1), (1, 0), (2, 2), (3, 3), (4, 1)])
            staged.append(revision_id)
            raise CommitInterrupted('candidate rows staged')

        interrupted = open_archive(self.path, before_commit=interrupt)
        with self.assertRaisesRegex(CommitInterrupted, 'candidate rows staged'):
            edit_day(interrupted, root, operations)
        self.assertEqual(len(staged), 1)
        reopened = open_archive(self.path)
        with self.assertRaises(LookupError):
            read_revision(reopened, staged[0])
        self.assertEqual(revision_ids(reopened), [root])
        self.assertEqual(ticket_ids(reopened), [ticket])
        self.assertEqual(revision_lines(read_revision(reopened, root)),
                         [[0, BATCH, 0, 10], [1, BATCH, 1, 20], [2, BATCH, 2, 30], [3, BATCH, 3, 40]])
        self.assertEqual(claim_lines(claim(reopened, ticket, root)),
                         [[1, 1, BATCH, 1, 20], [2, 2, BATCH, 2, 30]])

        retry = edit_day(reopened, root, operations)
        reopened = open_archive(self.path)
        self.assertEqual(revision_ids(reopened), [root, retry])
        self.assertEqual(read_revision(reopened, retry).parent_revision, root)
        self.assertEqual(revision_lines(read_revision(reopened, retry)),
                         [[0, BATCH, 1, 20], [1, BATCH, 0, 10], [2, BATCH, 2, 30],
                          [3, BATCH, 3, 40], [4, BATCH, 1, 20]])
        self.assertEqual(claim_lines(claim(reopened, ticket, retry)),
                         [[1, 0, BATCH, 1, 20], [2, 2, BATCH, 2, 30]])
