"""Jimms collection, manifest output and pagination behaviour."""
import argparse
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

from scraper.workers.jimms import JimmsCategoryDiscovery
from scraper.workers.jimms import JimmsCategoryDiscovery, page_url
from scraper.workers.jimms import JimmsPriceScraper


def options(**updates):
    values = dict(skip_scrape=False, skip_specs=False, cold=False, pages=1, delay=1.0,
                  jimms_input=None, jimms_category_url=None)
    values.update(updates)
    return argparse.Namespace(**values)

CATEGORY_HTML = ('<div id="initproductlist"><product-box>'
                 '<a href="/fi/Product/Show/123/gpu">GPU</a></product-box></div>')

PRODUCT_HTML = '<h1>MSI RTX 5070</h1><meta property="product:price:amount" content="299.99">'

HTML = '''<a href="/fi/Product/Show/999/recommended">Outside</a>
<div id="initproductlist"><product-box>
<a href="/fi/Product/Show/123/gpu">Image</a>
<a href="/fi/Product/Show/123/gpu?tracking=1#top">Name</a>
<a href="https://example.com/fi/Product/Show/456/other">External</a>
</product-box></div>'''

URL = 'https://www.jimms.fi/fi/Product/List/000-00P/gpu'


class JimmsWorkerTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

    def test_jimms_price_run_preserves_partial_success_and_closes_fetcher(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cached = root / 'data/raw/html/product.html'
            cached.parent.mkdir(parents=True)
            cached.write_text(PRODUCT_HTML)
            fetcher = Mock()
            fetcher.fetch.side_effect = [(PRODUCT_HTML, cached, 'cache'), ValueError('missing price')]
            manifest = [{'category': 'gpu', 'url': f'https://www.jimms.fi/product/{i}'} for i in range(2)]
            self.assertEqual(JimmsPriceScraper(manifest, root, fetcher).run(), 1)
            fetcher.close.assert_called_once()
            payload = json.loads(next((root / 'raw').glob('jimms_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            log = json.loads((root / 'raw/scrape_runs.jsonl').read_text())
            self.assertEqual(log['status'], 'partial')
            self.assertEqual(len(log['failures']), 1)

    def test_category_worker_writes_existing_manifest_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'manifest.json'
            fetcher = Mock()
            fetcher.fetch.return_value = (CATEGORY_HTML, Path(directory) / 'cache.html', 'cache')
            opts = options(url='https://www.jimms.fi/fi/Product/List/gpu', category='gpu', output=output)
            self.assertEqual(JimmsCategoryDiscovery(opts, fetcher).run(), 0)
            self.assertEqual(json.loads(output.read_text()), [
                {'category': 'gpu', 'url': 'https://www.jimms.fi/fi/Product/Show/123/gpu'}])
            fetcher.close.assert_called_once()


class CategoryDiscoveryTests(unittest.TestCase):
    def test_page_parameter(self):
        self.assertEqual(page_url(URL + '?page=5&sort=price#top', 2), URL + '?sort=price&page=2')

    def test_repeated_page_preserves_existing_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / 'urls.json'
            output.write_text('[{"existing": true}]')
            args = argparse.Namespace(category='gpu', url=URL, pages=2, output=output)
            from unittest.mock import Mock
            fetcher = Mock()
            fetcher.fetch.return_value = (HTML, root / 'cached.html', 'cache')
            self.assertEqual(JimmsCategoryDiscovery(args, fetcher).run(), 1)
            self.assertEqual(json.loads(output.read_text()), [{'existing': True}])
            self.assertIn('repeated listing', json.loads(output.with_suffix('.report.json').read_text())['failure']['error'])


if __name__ == '__main__':
    unittest.main()
