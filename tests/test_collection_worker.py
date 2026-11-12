"""Shared collection orchestration using a fake adapter, without retailer I/O."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.common.raw_data import RawProduct
from scraper.retailers.contracts import CategoryResult, ProductRequest, RetailerConfig, RetailerCapabilities, listing_page_url
from scraper.workers.collection_worker import CollectionWorker


class FakeAdapter:
    config = RetailerConfig('sample', 'Sample', 'https://sample.example',
        frozenset({'sample.example'}), {'gpu': '/gpu', 'cpu': '/cpu'}, RetailerCapabilities(True, True))

    def category_url(self, category):
        return self.config.category_url(category)

    def page_url(self, category, page, *, category_url=None):
        return listing_page_url(category_url or self.category_url(category), page)

    def parse_category(self, html, category, url):
        return self.results[html]

    def parse_product(self, html, request):
        return RawProduct('GPU', 100, request.url)


class CollectionWorkerTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / 'raw/html/page.html'
        self.path.parent.mkdir(parents=True)
        self.path.write_text('cached')
        self.fetcher = Mock()
        self.writer = Mock()
        self.adapter = FakeAdapter()
        self.adapter.results = {}

    def tearDown(self):
        self.context.close()

    def product(self, suffix='one'):
        return RawProduct('GPU', 100, 'https://sample.example/' + suffix)

    def run_worker(self, categories=('gpu',), pages=1, **kwargs):
        return CollectionWorker(self.adapter, self.root, self.fetcher, categories, pages,
                                raw_writer=self.writer, **kwargs).run()

    def test_complete_category_observations_need_no_product_requests(self):
        self.adapter.results['page'] = CategoryResult((self.product(),), site_total_products=25)
        self.fetcher.fetch.return_value = ('page', self.path, 'cache')
        result = self.run_worker()
        self.assertEqual((result.exit_code, result.pages_fetched, result.products_fetched, result.items_found), (0, 1, 0, 1))
        self.fetcher.fetch.assert_called_once_with('https://sample.example/gpu')
        self.fetcher.close.assert_called_once()
        self.assertEqual(self.writer.write.call_args.kwargs['site_total_products'], 25)
        self.assertEqual(json.loads((self.root / 'raw/scrape_runs.jsonl').read_text())['status'], 'ok')

    def test_follow_up_preserves_identifiers_and_product_source(self):
        request = ProductRequest('gpu', 'https://sample.example/product', '123', retailer_sku='SKU')
        self.adapter.results['page'] = CategoryResult(product_requests=(request, request))
        self.fetcher.fetch.side_effect = [('page', self.path, 'cache'), ('product', self.path, 'network')]
        result = self.run_worker()
        self.assertEqual((result.items_found, result.products_fetched, result.duplicates_skipped), (1, 1, 1))
        payload = self.writer.write.call_args.kwargs
        self.assertEqual(payload['source_type'], 'product')
        self.assertEqual(payload['source_url'], request.url)
        self.assertEqual(payload['origin'], 'network')
        self.assertEqual(payload['items'][0].external_id, '123')
        self.assertEqual(payload['items'][0].retailer_sku, 'SKU')

    def test_overlapping_products_are_not_written_twice(self):
        self.adapter.results = {'first': CategoryResult((self.product('one'), self.product('two'))),
                                'second': CategoryResult((self.product('two'), self.product('three')))}
        self.fetcher.fetch.side_effect = [('first', self.path, 'cache'), ('second', self.path, 'cache')]
        result = self.run_worker(pages=2)
        self.assertEqual((result.items_found, result.duplicates_skipped, result.exit_code), (3, 1, 0))
        self.assertEqual(len(self.writer.write.call_args_list[1].kwargs['items']), 1)

    def test_repeated_page_keeps_first_page_and_returns_partial(self):
        self.adapter.results['same'] = CategoryResult((self.product(),))
        self.fetcher.fetch.return_value = ('same', self.path, 'cache')
        result = self.run_worker(pages=2)
        self.assertEqual(result.status, 'partial')
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.items_found, 1)
        self.assertIn('repeated listing', result.failures[0].error)
        self.writer.write.assert_called_once()

    def test_category_failure_continues_next_category(self):
        self.adapter.results['cpu'] = CategoryResult((self.product(),))
        self.fetcher.fetch.side_effect = [ValueError('robots disallows'), ('cpu', self.path, 'cache')]
        result = self.run_worker(categories=('gpu', 'cpu'))
        self.assertEqual((result.exit_code, result.status, result.items_found), (1, 'partial', 1))
        self.assertEqual(result.failures[0].category, 'gpu')
        self.fetcher.close.assert_called_once()

    def test_unsupported_manifest_fails_before_fetch_and_closes(self):
        from dataclasses import replace
        self.adapter.config = replace(self.adapter.config, capabilities=RetailerCapabilities(True, False))
        with self.assertRaisesRegex(ValueError, 'does not support'):
            self.run_worker(categories=(), product_requests=(ProductRequest('gpu', 'https://sample.example/product'),))
        self.fetcher.fetch.assert_not_called()
        self.fetcher.close.assert_called_once()

    def test_unexpected_parser_failure_still_closes_fetcher(self):
        self.adapter.parse_category = Mock(side_effect=RuntimeError('unexpected'))
        self.fetcher.fetch.return_value = ('page', self.path, 'cache')
        with self.assertRaises(RuntimeError):
            self.run_worker()
        self.fetcher.close.assert_called_once()

    def test_new_registry_adapter_needs_no_cli_or_worker_branch(self):
        from scraper.cli import ScraperCLI
        from scraper.retailers.registry import RetailerRegistry
        from unittest.mock import patch
        self.adapter.results['page'] = CategoryResult((self.product(),))
        self.fetcher.fetch.return_value = ('page', self.path, 'cache')
        registry = RetailerRegistry({'sample': lambda: self.adapter})
        with patch('scraper.workers.collection.PageFetcher', return_value=self.fetcher):
            self.assertEqual(ScraperCLI(registry).run(['collect', '--shop', 'sample', '--all',
                                                     '--data-dir', str(self.root)]), 0)
        self.assertEqual(self.fetcher.fetch.call_count, 2)
        self.fetcher.close.assert_called_once()

    def test_writer_error_is_a_failure_and_fetcher_is_closed(self):
        self.adapter.results['page'] = CategoryResult((self.product(),))
        self.fetcher.fetch.return_value = ('page', self.path, 'cache')
        self.writer.write.side_effect = OSError('disk full')
        result = self.run_worker()
        self.assertEqual((result.exit_code, result.status, result.items_found), (1, 'failed', 0))
        self.fetcher.close.assert_called_once()

    def test_null_observation_does_not_suppress_explicit_follow_up(self):
        url = 'https://sample.example/product'
        self.adapter.results['page'] = CategoryResult(
            observations=(RawProduct('GPU', None, url),),
            product_requests=(ProductRequest('gpu', url, '123', retailer_sku='SKU'),))
        self.fetcher.fetch.side_effect = [('page', self.path, 'cache'), ('product', self.path, 'cache')]
        result = self.run_worker()
        self.assertEqual((result.exit_code, result.items_found, result.products_fetched), (0, 1, 1))
        self.assertEqual(self.writer.write.call_count, 1)
        self.assertEqual(result.counters.recovered_issues, 1)
        self.assertEqual(result.counters.null_price_observations, 0)
        self.assertEqual(self.writer.write.call_args.kwargs['items'][0].price_cents, 100)


if __name__ == '__main__':
    unittest.main()
