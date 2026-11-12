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

from scraper.workers.datatronic import DatatronicScraper

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
            worker = DatatronicScraper(['gpu'], project_root=root, fetcher=fetcher)
            self.assertEqual(worker.run(), 0)
            fetcher.close.assert_called_once()
            payload = json.loads(next((root / 'data/raw').glob('datatronic_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            self.assertEqual(payload['raw_html'], 'raw/html/product.html')

    def test_datatronic_failure_is_logged_and_fetcher_is_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fetcher = Mock()
            fetcher.fetch.side_effect = ValueError('robots.txt disallows URL')
            worker = DatatronicScraper(['gpu'], project_root=Path(directory), fetcher=fetcher)
            self.assertEqual(worker.run(), 1)
            fetcher.close.assert_called_once()
            self.assertEqual(json.loads(worker.run_log.read_text())['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
