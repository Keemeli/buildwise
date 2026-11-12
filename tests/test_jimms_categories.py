"""Category discovery checks without retailer requests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.retailers.jimms import parse_category
from scraper.workers.jimms import JimmsCategoryDiscovery, page_url
import argparse

URL = 'https://www.jimms.fi/fi/Product/List/000-00P/gpu'
HTML = '''<a href="/fi/Product/Show/999/recommended">Outside</a>
<div id="initproductlist"><product-box>
<a href="/fi/Product/Show/123/gpu">Image</a>
<a href="/fi/Product/Show/123/gpu?tracking=1#top">Name</a>
<a href="https://example.com/fi/Product/Show/456/other">External</a>
</product-box></div>'''


class CategoryTests(unittest.TestCase):
    def test_listing_scope_and_deduplication(self):
        self.assertEqual(parse_category(HTML, URL), ['https://www.jimms.fi/fi/Product/Show/123/gpu'])

    def test_missing_or_empty_listing_fails(self):
        for html in ('<h1>Blocked</h1>', '<div id="initproductlist"></div>'):
            with self.assertRaises(ValueError):
                parse_category(html, URL)

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
