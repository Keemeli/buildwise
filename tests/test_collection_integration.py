"""Real retailer adapters through collection, CLI and exact-page retries."""
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from scraper.cli import main
from scraper.pipeline.refresh import RefreshPipeline
from scraper.retailers.contracts import ProductRequest
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from scraper.retailers.proshop import ProshopAdapter
from scraper.workers.collection_worker import CollectionWorker

from tests.support import ROOT, response


DATATRONIC_LISTING_HTML = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
                '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
                '<span class="price">299,99 €</span></article></div><p>Yhteensä 1 tuotetta</p>')


class DatatronicWorkerTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

    def test_datatronic_worker_outputs_same_payload_and_closes_fetcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached = root / 'data/raw/html/product.html'
            cached.parent.mkdir(parents=True)
            cached.write_text(DATATRONIC_LISTING_HTML)
            fetcher = Mock()
            fetcher.fetch.return_value = (DATATRONIC_LISTING_HTML, cached, 'cache')
            worker = CollectionWorker(DatatronicAdapter(), root / 'data', fetcher, ['gpu'])
            self.assertEqual(worker.run().exit_code, 0)
            fetcher.close.assert_called_once()
            payload = json.loads(next((root / 'data/raw').glob('datatronic_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            self.assertEqual(payload['raw_html'], 'raw/html/product.html')
            self.assertEqual(payload['items'][0]['external_id'], '42')
            self.assertEqual((payload['source_type'], payload['page'], payload['site_total_products']), ('category', 1, 1))

    def test_datatronic_failure_is_logged_and_fetcher_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher = Mock()
            fetcher.fetch.side_effect = ValueError('robots.txt disallows URL')
            worker = CollectionWorker(DatatronicAdapter(), Path(directory) / 'data', fetcher, ['gpu'])
            self.assertEqual(worker.run().exit_code, 1)
            fetcher.close.assert_called_once()
            self.assertEqual(json.loads((worker.data_dir / 'raw/scrape_runs.jsonl').read_text())['status'], 'failed')

    def test_two_listing_pages_preserve_parser_fields_without_product_visits(self):
        from dataclasses import asdict
        from scraper.common.raw_data import RawProduct
        from scraper.retailers.datatronic import DatatronicParser
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / 'raw/html'
            cache.mkdir(parents=True)
            adapter, fetcher = DatatronicAdapter(), Mock()
            responses, expected = [], []
            for page in (1, 2):
                html = DATATRONIC_LISTING_HTML.replace('data-id-product="42"', f'data-id-product="{41 + page}"').replace(
                    'href="/gpu"', f'href="/gpu-{page}"').replace('Yhteensä 1 tuotetta', 'Yhteensä 100 tuotetta')
                path = cache / f'{page}.html'
                path.write_text(html)
                responses.append((html, path, 'cache'))
                items, total = DatatronicParser().parse_listing(html)
                expected.extend(asdict(RawProduct.from_item(item, 'listing_card')) for item in items)
            fetcher.fetch.side_effect = responses
            result = CollectionWorker(adapter, root, fetcher, ['gpu'], pages=2).run()
            self.assertEqual((result.exit_code, result.items_found, result.products_fetched), (0, 2, 0))
            self.assertEqual([call.args[0] for call in fetcher.fetch.call_args_list],
                             [adapter.page_url('gpu', page) for page in (1, 2)])
            actual = []
            for path in (root / 'raw').glob('datatronic_*.json'):
                document = json.loads(path.read_text())
                self.assertEqual(document['site_total_products'], total)
                actual.extend(document['items'])
            self.assertEqual(sorted(actual, key=lambda x: x['url']), sorted(expected, key=lambda x: x['url']))


class JimmsWorkerTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.path = self.root / 'raw/html/page.html'
        self.path.parent.mkdir(parents=True)
        self.path.write_text('<h1>GPU</h1><meta property="product:price:amount" content="299.99">')
        self.fetcher = Mock()
        self.adapter = JimmsAdapter()

    def tearDown(self):
        self.context.close()

    def test_manifest_partial_success_keeps_data_and_closes_fetcher(self):
        self.fetcher.fetch.side_effect = [(self.path.read_text(), self.path, 'cache'), ValueError('failed')]
        requests = tuple(ProductRequest('gpu', f'https://www.jimms.fi/fi/Product/Show/{i}/gpu',
                                        str(i), retailer_sku=f'SKU-{i}') for i in (123, 456))
        result = CollectionWorker(self.adapter, self.root, self.fetcher, product_requests=requests).run()
        self.assertEqual((result.exit_code, result.status, result.items_found), (1, 'partial', 1))
        self.fetcher.close.assert_called_once()
        item = json.loads(next((self.root / 'raw').glob('jimms_*.json')).read_text())['items'][0]
        self.assertEqual((item['external_id'], item['retailer_sku'], item['price_cents']), ('123', 'SKU-123', 29999))

    def test_50_gpu_products_use_only_two_category_responses(self):
        fixtures = ROOT / 'tests/fixtures/jimms'
        responses = []
        for page in (1, 2):
            path = self.path.parent / f'page{page}.html'
            shutil.copy2(fixtures / f'gpu_page_{page}.html', path)
            responses.append((path.read_text(), path, 'cache'))
        self.fetcher.fetch.side_effect = responses
        result = CollectionWorker(self.adapter, self.root, self.fetcher, ['gpu'], pages=2).run()
        self.assertEqual((result.exit_code, result.items_found, result.pages_fetched, result.products_fetched), (0, 50, 2, 0))
        self.assertEqual([call.args[0] for call in self.fetcher.fetch.call_args_list],
                         [self.adapter.page_url('gpu', page) for page in (1, 2)])
        expected = json.loads((fixtures / 'expected_products.json').read_text())
        actual = []
        for path in (self.root / 'raw').glob('jimms_*.json'):
            document = json.loads(path.read_text())
            self.assertEqual((document['source_type'], document['item_count']), ('category', 25))
            actual.extend({'page': document['page'], **{key: item[key] for key in
                ('name', 'url', 'price_cents', 'external_id', 'retailer_sku')}} for item in document['items'])
        self.assertEqual(sorted(actual, key=lambda x: x['url']), sorted(expected, key=lambda x: x['url']))


    def test_repeated_page_keeps_saved_observations_unchanged(self):
        html = (ROOT / 'tests/fixtures/jimms/gpu_page_1.html').read_text()
        self.path.write_text(html)
        self.fetcher.fetch.return_value = (html, self.path, 'cache')
        existing = self.root / 'raw/previous.json'
        existing.write_text('{"previous": true}')
        result = CollectionWorker(self.adapter, self.root, self.fetcher, ['gpu'], pages=2).run()
        self.assertEqual((result.exit_code, result.status, result.items_found), (1, 'partial', 25))
        self.assertEqual(existing.read_text(), '{"previous": true}')
        self.assertIn('repeated listing', result.failures[0].error)

    def test_missing_category_price_follows_only_that_product(self):
        category = ('<div id="initproductlist"><product-box><h5 class="product-box-name">'
                    '<a href="/fi/Product/Show/123/gpu">GPU</a></h5>'
                    '<div class="product-box-sku">SKU-123</div></product-box></div>')
        category_path = self.path.parent / 'category.html'
        category_path.write_text(category)
        self.fetcher.fetch.side_effect = [(category, category_path, 'cache'), (self.path.read_text(), self.path, 'cache')]
        result = CollectionWorker(self.adapter, self.root, self.fetcher, ['gpu']).run()
        self.assertEqual((result.exit_code, result.items_found, result.products_fetched), (0, 1, 1))
        self.assertEqual([call.args[0] for call in self.fetcher.fetch.call_args_list],
                         [self.adapter.page_url('gpu', 1), 'https://www.jimms.fi/fi/Product/Show/123/gpu'])
        document = json.loads(next((self.root / 'raw').glob('jimms_*.json')).read_text())
        self.assertEqual(document['source_type'], 'product')
        self.assertIsNone(document['page'])
        self.assertEqual(document['raw_html'], 'raw/html/page.html')
        self.assertEqual((document['items'][0]['external_id'], document['items'][0]['retailer_sku']), ('123', 'SKU-123'))


PROSHOP_FIXTURES = Path(__file__).parent / 'fixtures/proshop'


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
            self.cache(url, (PROSHOP_FIXTURES / f'gpu_page_{page}.html').read_text())
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
        self.cache(self.urls[0], (PROSHOP_FIXTURES / 'gpu_page_1.html').read_text())
        self.assertEqual(self.collect(), 1)
        self.assertEqual(self.reports()[0]['status'], 'partial')
        entry = self.entries()[0]
        self.assertEqual(entry['latest_outcome']['page'], 2)
        self.assertEqual(entry['url'], self.urls[1])
        originals = {path: path.read_bytes() for path in (self.root / 'raw').glob('*.json')}
        self.cache(self.urls[1], (PROSHOP_FIXTURES / 'gpu_page_2.html').read_text())
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
        self.cache(self.urls[0], (PROSHOP_FIXTURES / 'gpu_page_1.html').read_text())
        original = (PROSHOP_FIXTURES / 'gpu_page_2.html').read_text()
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
        soup = BeautifulSoup((PROSHOP_FIXTURES / 'gpu_page_1.html').read_text(), 'html.parser')
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
        rules = (PROSHOP_FIXTURES / 'robots.txt').read_text()
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
        self.cache(self.urls[0], (PROSHOP_FIXTURES / 'gpu_page_1.html').read_text())
        self.assertEqual(self.collect(pages=1), 0)
        product = json.loads((PROSHOP_FIXTURES / 'observations.json').read_text())['products'][0]
        self.cache(product['source_url'], (PROSHOP_FIXTURES / 'product_3331069.html').read_text())
        self.assertEqual(main(['specs', '--shop', 'proshop', '--category', 'gpu', '--limit', '1',
            '--raw-dir', str(self.root / 'raw'), '--out', str(self.root / 'out'), '--offline']), 0)
        entry = json.loads((self.root / 'out/specs.json').read_text())['items'][product['source_url']]
        self.assertEqual(entry['specs']['recommended_psu_w'], 1000)
        self.assertEqual(entry['specs']['length_mm'], 357.6)
        self.assertIsNone(entry['specs']['power_w'])


if __name__ == '__main__':
    unittest.main()
