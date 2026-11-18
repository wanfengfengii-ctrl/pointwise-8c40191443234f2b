from decimal import Decimal
import json

from catalog.snapshots import read_revision
from catalog.transactions import open_archive
from delivery.export import export
from intake.batches import read_batch
from review.claims import claim
from review.tickets import mark
from revision.coordinates import Delete, Move
from revision.publish import edit_day, seal_day
from tests.support import ArchiveTestCase, BATCH, DAY, claim_lines, freeze, run_reopened


class DeliveryTests(ArchiveTestCase):
    def _moved_readings(self):
        root = freeze(self.archive, [0, None, 7, 7])
        window = mark(self.archive, root, 0, 2)
        missing = mark(self.archive, root, 1, 2)
        moved = edit_day(self.archive, root, [Move(1, 0)])
        withdrawn = edit_day(self.archive, moved, [Delete(0)])
        return window, missing, moved, withdrawn

    def test_fixed_coordinates(self):
        ticket, _, moved, _ = self._moved_readings()
        first, second = run_reopened('exports', self.path, moved, ticket, ticket)
        reopened = open_archive(self.path)
        self.assertEqual(first, second)
        self.assertEqual(first.encode('utf-8'), export(reopened, ticket, moved))
        self.assertEqual(claim_lines(claim(reopened, ticket, moved)),
                         [[1, 0, BATCH, 1, None], [0, 1, BATCH, 0, 0]])
        document = json.loads(first)
        self.assertEqual(document, {
            'ticket_id': ticket,
            'target_revision': moved,
            'rows': [
                {'marked_position': 1, 'target_position': 0,
                 'source': {'batch_id': BATCH, 'position': 1}, 'value': None},
                {'marked_position': 0, 'target_position': 1,
                 'source': {'batch_id': BATCH, 'position': 0}, 'value': 0},
            ],
            'totals': {'row_count': 2, 'missing_count': 1},
        })
        independent = [row['value'] for row in document['rows']]
        self.assertEqual(document['totals']['row_count'], len(independent))
        self.assertEqual(document['totals']['missing_count'], independent.count(None))

    def test_zero_and_missing(self):
        ticket, missing, moved, withdrawn = self._moved_readings()
        moved_text, missing_text = run_reopened('exports', self.path, moved, ticket, missing)
        moved_doc = json.loads(moved_text)
        self.assertEqual(moved_doc['totals'], {'row_count': 2, 'missing_count': 1})
        self.assertEqual([row['value'] for row in moved_doc['rows']], [None, 0])
        self.assertEqual(json.loads(missing_text)['totals'], {'row_count': 1, 'missing_count': 1})
        empty_text, = run_reopened('exports', self.path, withdrawn, missing)
        self.assertEqual(json.loads(empty_text), {
            'ticket_id': missing, 'target_revision': withdrawn, 'rows': [],
            'totals': {'row_count': 0, 'missing_count': 0},
        })
        self.assertEqual(claim(open_archive(self.path), missing, withdrawn).rows, ())

    def test_target_scope(self):
        root = freeze(self.archive, [6, 0])
        marked = edit_day(self.archive, root, [Move(1, 0)])
        ticket = mark(self.archive, marked, 0, 1)
        child = edit_day(self.archive, marked, [Move(0, 2)])
        other_day = freeze(self.archive, [0], day='2026-11-19', batch='track-b')
        same_day_unrelated = seal_day(self.archive, DAY, BATCH)
        self.assertGreater(other_day, marked)
        self.assertGreater(same_day_unrelated, marked)
        for interface in (claim, export):
            for target in (root, other_day, same_day_unrelated):
                with self.subTest(interface=interface.__name__, target=target):
                    with self.assertRaisesRegex(ValueError, 'outside the lineage'):
                        interface(self.archive, ticket, target)
            with self.assertRaises(LookupError):
                interface(self.archive, ticket, same_day_unrelated + 1)
            with self.assertRaises(LookupError):
                interface(self.archive, ticket + 1, marked)

        self.assertEqual(claim_lines(claim(self.archive, ticket, marked)), [[0, 0, BATCH, 1, 0]])
        self.assertEqual(claim_lines(claim(self.archive, ticket, child)), [[0, 1, BATCH, 1, 0]])
        self.assertEqual(json.loads(export(self.archive, ticket, marked))['target_revision'], marked)
        accepted = json.loads(export(self.archive, ticket, child))
        self.assertEqual(accepted['target_revision'], child)
        self.assertEqual(accepted['rows'][0]['target_position'], 1)
        self.assertEqual(accepted['totals'], {'row_count': 1, 'missing_count': 0})

    def test_exact_integer_roundtrip(self):
        values = [10 ** 5000 + 17, -(2 ** 100 + 3)]
        batch_id = '巡检-"甲"'
        root = freeze(self.archive, values, batch=batch_id)
        ticket = mark(self.archive, root, 0, 2)
        reopened = open_archive(self.path)
        self.assertEqual([row.value for row in read_batch(reopened, batch_id).rows], values)
        self.assertEqual([row.value for row in read_revision(reopened, root).rows], values)
        self.assertEqual([row.value for row in claim(reopened, ticket, root).rows], values)
        document = json.loads(export(reopened, ticket, root), parse_int=Decimal)
        for position, (encoded, expected) in enumerate(zip(document['rows'], values, strict=True)):
            self.assertIsInstance(encoded['value'], Decimal)
            self.assertEqual(encoded['value'], expected)
            self.assertEqual(encoded['source'], {'batch_id': batch_id, 'position': position})
        self.assertEqual(document['totals'], {'row_count': 2, 'missing_count': 0})
