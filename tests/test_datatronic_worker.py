"""Datatronic collection, raw output and failure handling."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.workers.collection_worker import CollectionWorker
from scraper.retailers.datatronic import DatatronicAdapter

LISTING_HTML = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
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
            cached.write_text(LISTING_HTML)
            fetcher = Mock()
            fetcher.fetch.return_value = (LISTING_HTML, cached, 'cache')
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
                html = LISTING_HTML.replace('data-id-product="42"', f'data-id-product="{41 + page}"').replace(
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


if __name__ == '__main__':
    unittest.main()
