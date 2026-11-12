"""Proshop CLI collection and exact-page retries using saved HTML only."""
import contextlib
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

from scraper.cli import main
from scraper.retailers.proshop import ProshopAdapter
from scraper.pipeline.refresh import RefreshPipeline
from test_collection_policy_matrix import response

FIXTURES = Path(__file__).parent / 'fixtures/proshop'


class ProshopCollectionTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.context.enter_context(patch('requests.Session.get', side_effect=AssertionError('live requests forbidden')))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.adapter = ProshopAdapter()
        self.urls = [self.adapter.page_url('gpu', page) for page in (1, 2)]

    def cache(self, url, html, timestamp=1700000000):
        path = self.root / 'raw/html/proshop' / date.today().isoformat() / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        os.utime(path, (timestamp, timestamp))

    def collect(self, pages=2, *extra):
        return main(['collect', '--shop', 'proshop', '--category', 'gpu', '--pages', str(pages),
                     '--data-dir', str(self.root), '--offline', *extra])

    def reports(self):
        return [json.loads(line) for line in (self.root / 'raw/scrape_runs.jsonl').read_text().splitlines()]

    def entries(self):
        return list(json.loads((self.root / 'pending/collection.json').read_text())['entries'].values())

    def raw(self):
        return [json.loads(path.read_text()) for path in (self.root / 'raw').glob('proshop_*.json')]

    def test_two_pages_save_48_regular_products_and_report_two_exclusions(self):
        for page, url in enumerate(self.urls, 1):
            self.cache(url, (FIXTURES / f'gpu_page_{page}.html').read_text())
        self.assertEqual(self.collect(), 0)
        report = self.reports()[0]
        self.assertEqual((report['items_found'], report['counters']['excluded_products']), (48, 2))
        self.assertEqual(report['counters']['cache_hits'], 2)
        self.assertEqual(report['counters']['product_followups_attempted'], 0)
        self.assertEqual({item['external_id'] for item in report['exclusions']}, {'3203171d', '3482347d'})
        self.assertEqual({item['reason'] for item in report['exclusions']}, {'demo_listing'})
        self.assertEqual(report['failures'], [])
        self.assertFalse((self.root / 'pending/collection.json').exists())
        documents = self.raw()
        self.assertEqual({doc['page'] for doc in documents}, {1, 2})
        self.assertEqual(sum(len(doc['items']) for doc in documents), 48)
        self.assertEqual({doc['schema_version'] for doc in documents}, {2})
        self.assertEqual({doc['fetched_at'] for doc in documents}, {'2023-11-14T22:13:20+00:00'})
        self.assertEqual({doc['run_id'] for doc in documents}, {report['run_id']})
        self.assertEqual(main(['normalise', '--raw-dir', str(self.root / 'raw'), '--out', str(self.root / 'normalised')]), 0)
        catalogue = json.loads((self.root / 'normalised/components.json').read_text())
        listings = [listing for component in catalogue['components'] for listing in component['listings']]
        self.assertEqual(len(listings), 48)
        self.assertEqual({listing['shop'] for listing in listings}, {'Proshop'})

    def test_missing_second_page_retries_exact_pn_url_and_preserves_page_metadata(self):
        self.cache(self.urls[0], (FIXTURES / 'gpu_page_1.html').read_text())
        self.assertEqual(self.collect(), 1)
        self.assertEqual(self.reports()[0]['status'], 'partial')
        entry = self.entries()[0]
        self.assertEqual(entry['latest_outcome']['page'], 2)
        self.assertEqual(entry['url'], self.urls[1])
        originals = {path: path.read_bytes() for path in (self.root / 'raw').glob('*.json')}
        self.cache(self.urls[1], (FIXTURES / 'gpu_page_2.html').read_text())
        # Exact retry requests must never call a page-URL builder, regardless of
        # the adapter's parameter spelling or pagination implementation.
        with patch.object(ProshopAdapter, 'page_url', side_effect=AssertionError('reconstructed retry URL')):
            self.assertEqual(main(['retry', '--shop', 'proshop', '--data-dir', str(self.root), '--offline']), 0)
        self.assertEqual(self.entries()[0]['status'], 'resolved')
        retry = next(doc for doc in self.raw() if doc['run_id'] == self.reports()[-1]['run_id'])
        self.assertEqual((retry['page'], retry['source_url']), (2, self.urls[1]))
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)

    def test_missing_category_price_retries_same_source_page_and_resolves_product(self):
        self.cache(self.urls[0], (FIXTURES / 'gpu_page_1.html').read_text())
        original = (FIXTURES / 'gpu_page_2.html').read_text()
        soup = BeautifulSoup(original, 'html.parser')
        card = soup.select_one('#products > li')
        product_id = card.select_one('input[name=productId]')['value']
        card.select_one('.site-currency-lg').decompose()
        self.cache(self.urls[1], str(soup))
        self.assertEqual(self.collect(), 1)
        entry = self.entries()[0]
        self.assertEqual((entry['kind'], entry['latest_outcome']['page']), ('product', 2))
        self.assertEqual(entry['latest_outcome']['source_url'], self.urls[1])
        self.assertEqual(entry['latest_outcome']['external_id'], product_id)
        self.assertEqual(self.reports()[0]['counters']['null_price_observations'], 1)
        self.cache(self.urls[1], original, timestamp=1700003600)
        self.assertEqual(main(['retry', '--shop', 'proshop', '--data-dir', str(self.root), '--offline']), 0)
        self.assertEqual(self.entries()[0]['status'], 'resolved')
        self.assertEqual(self.reports()[-1]['counters']['product_followups_attempted'], 0)
        latest = next(doc for doc in self.raw() if doc['run_id'] == self.reports()[-1]['run_id'])
        self.assertEqual((latest['page'], latest['source_url']), (2, self.urls[1]))
        self.assertIsNotNone(next(item for item in latest['items'] if item['external_id'] == product_id)['price_cents'])

    def test_all_demo_page_is_explicitly_excluded_without_empty_page_failure(self):
        soup = BeautifulSoup((FIXTURES / 'gpu_page_1.html').read_text(), 'html.parser')
        for card in soup.select('#products > li'):
            if not card.select_one('input[name=productId]')['value'].endswith('d'):
                card.decompose()
        self.cache(self.urls[0], str(soup))
        self.assertEqual(self.collect(pages=1), 0)
        report = self.reports()[0]
        self.assertEqual((report['items_found'], report['counters']['excluded_products']), (0, 2))
        self.assertEqual(report['counters']['category_pages_processed'], 1)
        self.assertEqual(report['failures'], [])
        self.assertEqual(len(report['exclusions']), 2)
        self.assertEqual(self.raw(), [])

    def test_disallowed_query_is_blocked_before_category_request(self):
        rules = (FIXTURES / 'robots.txt').read_text()
        with patch('requests.Session.get', side_effect=lambda url, **kwargs: response(rules, url)) as get:
            self.assertEqual(main(['collect', '--shop', 'proshop', '--category', 'gpu', '--url',
                self.urls[0] + '?page=2', '--data-dir', str(self.root), '--force']), 1)
        self.assertEqual(get.call_count, 1)
        self.assertTrue(get.call_args.args[0].endswith('/robots.txt'))
        self.assertEqual(self.reports()[0]['failures'][0]['retry_classification'], 'blocked')
        self.assertEqual(self.raw(), [])

    def test_refresh_includes_shared_specifications_and_cli_parses_saved_page(self):
        from argparse import Namespace
        options = Namespace(pages=2, delay=1, skip_scrape=False, skip_specs=False, cold=False)
        pipeline = RefreshPipeline(options, ['gpu'], ['proshop'], project_root=self.root)
        self.assertEqual([name for name, _ in pipeline.build_stages()], ['proshop-collect', 'proshop-specs', 'normalise', 'export'])
        self.cache(self.urls[0], (FIXTURES / 'gpu_page_1.html').read_text())
        self.assertEqual(self.collect(pages=1), 0)
        product = json.loads((FIXTURES / 'observations.json').read_text())['products'][0]
        self.cache(product['source_url'], (FIXTURES / 'product_3331069.html').read_text())
        self.assertEqual(main(['specs', '--shop', 'proshop', '--category', 'gpu', '--limit', '1',
            '--raw-dir', str(self.root / 'raw'), '--out', str(self.root / 'out'), '--offline']), 0)
        entry = json.loads((self.root / 'out/specs.json').read_text())['items'][product['source_url']]
        self.assertEqual(entry['specs']['recommended_psu_w'], 1000)
        self.assertEqual(entry['specs']['length_mm'], 357.6)
        self.assertIsNone(entry['specs']['power_w'])


if __name__ == '__main__':
    unittest.main()
