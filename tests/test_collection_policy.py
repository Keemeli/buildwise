"""Checkpoint 2 implementation checks for null preservation and run reporting."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.common.raw_data import RawProduct
from scraper.retailers.contracts import CategoryResult, ProductRequest, RetailerConfig, RetailerCapabilities
from scraper.workers.collection_worker import CollectionWorker


class CollectionPolicyImplementationTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / 'raw/html/category.html'
        self.path.parent.mkdir(parents=True)
        self.path.write_text('saved source')
        os.utime(self.path, (1700000000, 1700000000))
        self.adapter = Mock()
        self.adapter.config = RetailerConfig('sample', 'Sample', 'https://shop.example',
            frozenset({'shop.example'}), {'gpu': '/gpu'}, RetailerCapabilities(True, True))
        self.adapter.category_url.return_value = 'https://shop.example/gpu'
        self.adapter.page_url.return_value = 'https://shop.example/gpu'
        self.fetcher = Mock()
        self.product = RawProduct('GPU', None, 'https://shop.example/product', '123', retailer_sku='SKU')

    def tearDown(self):
        self.context.close()

    def run_worker(self):
        return CollectionWorker(self.adapter, self.root, self.fetcher, ['gpu']).run()

    def test_all_null_run_is_partial_and_raw_report_share_run_id(self):
        self.adapter.parse_category.return_value = CategoryResult((self.product,))
        self.fetcher.fetch.return_value = ('source', self.path, 'cache')
        result = self.run_worker()
        document = json.loads(next((self.root / 'raw').glob('sample_*.json')).read_text())
        record = json.loads((self.root / 'raw/scrape_runs.jsonl').read_text())
        self.assertEqual((result.status, result.exit_code), ('partial', 1))
        self.assertIsNone(document['items'][0]['price_cents'])
        self.assertEqual(document['run_id'], result.run_id)
        self.assertEqual(record['run_id'], result.run_id)
        self.assertEqual(document['fetched_at'], '2023-11-14T22:13:20+00:00')
        self.assertEqual(result.counters.null_price_observations, 1)
        self.assertEqual(result.counters.cache_hits, 1)
        self.assertEqual(result.counters.unresolved_outcomes, 1)
        self.assertEqual(result.coverage[0]['reason'], 'page_limit')
        pending = json.loads((self.root / 'pending/collection.json').read_text())
        entry = next(iter(pending['entries'].values()))
        self.assertEqual(entry['latest_outcome']['run_id'], result.run_id)
        self.assertEqual(entry['latest_outcome']['external_id'], '123')
        self.assertEqual(entry['sightings'][0]['source_context']['raw_html'], 'raw/html/category.html')
        self.assertTrue(entry['retry_eligible'])

    def test_failed_fallback_keeps_identified_null_and_one_unresolved_outcome(self):
        request = ProductRequest('gpu', self.product.url, '123', retailer_sku='SKU')
        self.adapter.parse_category.return_value = CategoryResult((self.product,), (request,))
        self.fetcher.fetch.side_effect = [('source', self.path, 'cache'), requests.Timeout('timeout')]
        result = self.run_worker()
        self.assertEqual((result.status, result.items_found), ('partial', 1))
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(result.failures[0].reason, 'connection_failure')
        self.assertEqual(result.failures[0].retry_classification, 'retryable')
        self.assertEqual(result.failures[0].external_id, '123')
        self.assertEqual(result.failures[0].retailer_sku, 'SKU')
        self.assertEqual(result.counters.source_failures, 1)
        self.assertEqual(result.counters.product_followups_attempted, 1)
        document = json.loads(next((self.root / 'raw').glob('sample_*.json')).read_text())
        self.assertEqual(document['source_type'], 'category')
        self.assertIsNone(document['items'][0]['price_cents'])

    def test_recovered_fallback_saves_only_priced_observation(self):
        request = ProductRequest('gpu', self.product.url, '123', retailer_sku='SKU')
        self.adapter.parse_category.return_value = CategoryResult((self.product,), (request,))
        self.adapter.parse_product.return_value = RawProduct('GPU', 29999, request.url)
        self.fetcher.fetch.side_effect = [('category', self.path, 'cache'), ('product', self.path, 'cache')]
        result = self.run_worker()
        self.assertEqual((result.status, result.exit_code), ('ok', 0))
        self.assertEqual((result.counters.recovered_issues, result.counters.unresolved_outcomes), (1, 0))
        self.assertEqual((result.counters.observations_saved, result.counters.null_price_observations), (1, 0))
        self.assertEqual(len(list((self.root / 'raw').glob('sample_*.json'))), 1)

    def test_confirmed_empty_end_is_success_and_does_not_claim_page_limit(self):
        self.adapter.parse_category.return_value = CategoryResult(end_of_category=True, end_reason='published_total_zero')
        self.fetcher.fetch.return_value = ('source', self.path, 'cache')
        result = self.run_worker()
        self.assertEqual((result.status, result.exit_code, result.items_found), ('ok', 0, 0))
        self.assertEqual(result.coverage[0]['reason'], 'confirmed_end')
        self.assertEqual(result.counters.category_pages_processed, 1)


if __name__ == '__main__':
    unittest.main()
