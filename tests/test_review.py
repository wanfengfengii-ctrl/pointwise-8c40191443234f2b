from catalog.snapshots import read_revision
from catalog.transactions import open_archive
from review.claims import claim
from review.tickets import mark
from revision.coordinates import Copy, Delete, Move
from revision.publish import edit_day
from tests.support import (
    ArchiveTestCase, BATCH, claim_lines, freeze, revision_lines, run_reopened,
)


class ReviewTests(ArchiveTestCase):
    def test_frozen_survival(self):
        root = freeze(self.archive, [10, 20, 30, 40])
        ticket = mark(self.archive, root, 1, 3)
        moved = edit_day(self.archive, root, [Copy(1, 4), Move(1, 0)])
        copy_ticket = mark(self.archive, moved, 4, 5)
        withdrawn = edit_day(self.archive, moved, [Delete(0)])

        self.assertEqual(revision_lines(read_revision(self.archive, moved)),
                         [[0, BATCH, 1, 20], [1, BATCH, 0, 10], [2, BATCH, 2, 30],
                          [3, BATCH, 3, 40], [4, BATCH, 1, 20]])
        self.assertEqual(revision_lines(read_revision(self.archive, withdrawn)),
                         [[0, BATCH, 0, 10], [1, BATCH, 2, 30], [2, BATCH, 3, 40], [3, BATCH, 1, 20]])
        initial = claim(self.archive, ticket, root)
        self.assertEqual((initial.ticket_id, initial.target_revision), (ticket, root))
        self.assertEqual(claim_lines(initial), [[1, 1, BATCH, 1, 20], [2, 2, BATCH, 2, 30]])
        self.assertEqual(claim_lines(claim(self.archive, ticket, moved)),
                         [[1, 0, BATCH, 1, 20], [2, 2, BATCH, 2, 30]],
                         'v6.frozen_survival: moved origin and C are the only selected rows')
        self.assertEqual(claim_lines(claim(self.archive, ticket, withdrawn)),
                         [[2, 1, BATCH, 2, 30]],
                         'v6.frozen_survival: withdrawn origin ends its old selection')
        self.assertEqual(claim_lines(claim(self.archive, copy_ticket, withdrawn)), [[4, 3, BATCH, 1, 20]])

    def test_paired_deletes(self):
        observed = []
        visible = []
        for deleted_index in (0, 1):
            path = self.directory / f'delete-{deleted_index}.sqlite3'
            archive = open_archive(path)
            root = freeze(archive, [20])
            copied = edit_day(archive, root, [Copy(0, 1)])
            original_ticket = mark(archive, copied, 0, 1)
            copy_ticket = mark(archive, copied, 1, 2)
            self.assertEqual(claim_lines(claim(archive, original_ticket, copied)), [[0, 0, BATCH, 0, 20]])
            self.assertEqual(claim_lines(claim(archive, copy_ticket, copied)), [[1, 1, BATCH, 0, 20]])
            target = edit_day(archive, copied, [Delete(deleted_index)])
            visible.append(run_reopened('revision', path, target))
            observed.append(run_reopened('claims', path, target, original_ticket, copy_ticket))

        self.assertEqual(visible, [[[0, BATCH, 0, 20]], [[0, BATCH, 0, 20]]])
        self.assertEqual(observed, [[[], [[1, 0, BATCH, 0, 20]]], [[[0, 0, BATCH, 0, 20]], []]],
                         'v6.paired_deletes: identical visible rows must yield opposite surviving tickets')

    def test_target_order(self):
        root = freeze(self.archive, [10, 20, 30, 40])
        ticket = mark(self.archive, root, 1, 3)
        child = edit_day(self.archive, root, [Move(2, 0)])
        self.assertEqual(revision_lines(read_revision(self.archive, child)),
                         [[0, BATCH, 2, 30], [1, BATCH, 0, 10], [2, BATCH, 1, 20], [3, BATCH, 3, 40]])
        self.assertEqual(claim_lines(claim(self.archive, ticket, child)),
                         [[2, 0, BATCH, 2, 30], [1, 2, BATCH, 1, 20]])
