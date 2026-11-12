"""Jimms adapter integration through the shared collection worker."""
import contextlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.retailers.jimms import JimmsAdapter
from scraper.retailers.contracts import ProductRequest, listing_page_url
from scraper.workers.collection_worker import CollectionWorker


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

    def test_page_parameter_replaces_old_value_and_retains_filters(self):
        url = self.adapter.category_url('gpu')
        self.assertEqual(listing_page_url(url + '?page=5&sort=price#top', 2), url + '?sort=price&page=2')

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


if __name__ == '__main__':
    unittest.main()
