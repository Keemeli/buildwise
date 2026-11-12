"""Checkpoint 1 persistence, identity and failure-safety checks."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scraper.workers.collection_reporting import CollectionOutcome
from scraper.workers.pending_work import PendingWorkStore


class PendingWorkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = PendingWorkStore(Path(self.directory.name))
        self.outcome = CollectionOutcome('run1', 'Jimms', 'product', 'gpu',
            'https://shop/product', 'https://shop/category', 'missing_price',
            'retryable', 'missing price', '123', 'SKU')

    def record(self, outcome=None, kind='product', context=None):
        outcome = outcome or self.outcome
        result = SimpleNamespace(shop=outcome.shop, run_id=outcome.run_id, finished_at='2026-11-10T00:00:00Z')
        self.store.record(result, {(kind, outcome.category, outcome.url): outcome},
                          {outcome.url: context} if context else None)

    def entries(self):
        return json.loads(self.store.path.read_text())['entries']

    def test_overlapping_categories_and_runs_keep_one_product_and_evidence(self):
        self.record(context={'raw_html': 'raw/html/category.html', 'page': 1})
        self.record(replace(self.outcome, run_id='run2', category='cpu'))
        self.record(replace(self.outcome, run_id='run2', category='cpu'))
        entries = self.entries()
        self.assertEqual(len(entries), 1)
        entry = next(iter(entries.values()))
        self.assertEqual(len(entry['sightings']), 2)
        self.assertEqual(entry['first_run_id'], 'run1')
        self.assertEqual(entry['last_run_id'], 'run2')
        self.assertEqual(entry['sightings'][0]['source_context']['page'], 1)
        self.assertEqual(entry['latest_outcome']['retailer_sku'], 'SKU')

    def test_retailers_and_category_work_have_distinct_identities(self):
        self.record()
        self.record(replace(self.outcome, shop='Datatronic'))
        self.record(kind='category')
        self.record(replace(self.outcome, category='cpu'), kind='category')
        self.assertEqual(len(self.entries()), 4)

    def test_all_classifications_retained_only_retryable_eligible(self):
        for classification in ('retryable', 'inspect', 'blocked', 'unavailable'):
            self.record(replace(self.outcome, url='https://shop/' + classification,
                                retry_classification=classification))
        entries = list(self.entries().values())
        self.assertEqual(len(entries), 4)
        self.assertEqual(sum(e['retry_eligible'] for e in entries), 1)
        self.assertTrue(all(e['status'] == 'pending' for e in entries))

    def test_no_outcomes_does_not_create_or_resolve_entries(self):
        result = SimpleNamespace()
        self.store.record(result, {})
        self.assertFalse(self.store.path.exists())
        self.record()
        before = self.store.path.read_bytes()
        self.store.record(result, {})
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_corrupt_or_unknown_store_is_not_overwritten(self):
        self.store.path.parent.mkdir(parents=True)
        for text in ('broken JSON', '{"schema_version": 99, "entries": {}}'):
            self.store.path.write_text(text)
            with self.assertRaises(ValueError):
                self.record()
            self.assertEqual(self.store.path.read_text(), text)

    def test_failed_atomic_replace_preserves_previous_store(self):
        self.record()
        before = self.store.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                self.record(replace(self.outcome, run_id='run2'))
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(list(self.store.path.parent.glob('*.tmp')), [])

    def test_interrupted_attempt_is_retained_before_next_attempt(self):
        self.record()
        key = next(iter(self.entries()))
        self.store.start_attempt(key, 'attempt1', 'start1')
        self.store.start_attempt(key, 'attempt2', 'start2')
        attempts = self.entries()[key]['attempts']
        self.assertEqual([a['status'] for a in attempts], ['interrupted', 'running'])
        self.assertEqual(attempts[0]['finished_at'], 'start2')

    def test_newer_collection_failure_prevents_stale_retry_resolution(self):
        self.record()
        key = next(iter(self.entries()))
        self.store.start_attempt(key, 'attempt1', 'start')
        self.record(replace(self.outcome, run_id='newer'))
        result = SimpleNamespace(run_id='retry', status='ok',
                                 counters=SimpleNamespace(unresolved_outcomes=0))
        resolved = self.store.finish_attempt(key, 'attempt1', 'finish', result=result,
                                            resolved=True, expected_run_id='run1')
        self.assertFalse(resolved)
        entry = self.entries()[key]
        self.assertEqual(entry['status'], 'pending')
        self.assertEqual(entry['last_run_id'], 'newer')
        self.assertEqual(entry['attempts'][0]['status'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
