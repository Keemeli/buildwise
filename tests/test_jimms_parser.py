"""Jimms HTML product and category parsing."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.retailers.jimms import parse_category
from scraper.retailers.jimms import parse_product

HTML = '''<a href="/fi/Product/Show/999/recommended">Outside</a>
<div id="initproductlist"><product-box>
<a href="/fi/Product/Show/123/gpu">Image</a>
<a href="/fi/Product/Show/123/gpu?tracking=1#top">Name</a>
<a href="https://example.com/fi/Product/Show/456/other">External</a>
</product-box></div>'''

URL = 'https://www.jimms.fi/fi/Product/List/000-00P/gpu'


class ProductParsingTests(unittest.TestCase):
    def test_metadata_and_fallback(self):
        for markup in ('<meta property="product:price:amount" content="1234.56">',
                       '<span itemprop="price" content="1 234,56"></span>'):
            result = parse_product('<h1>Example GPU</h1>' + markup)
            self.assertEqual((result['name'], result['price_cents']), ('Example GPU', 123456))

    def test_invalid_pages(self):
        for html in ('<h1>GPU</h1>', '<meta itemprop="price" content="10">',
                     '<h1>GPU</h1><meta itemprop="price" content="free">',
                     '<h1>GPU</h1><meta itemprop="price" content="10"><meta itemprop="price" content="20">',
                     '<h1>GPU</h1><meta itemprop="price" content="10"><meta itemprop="priceCurrency" content="USD">'):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_product(html)


class CategoryParsingTests(unittest.TestCase):
    def test_listing_scope_and_deduplication(self):
        self.assertEqual(parse_category(HTML, URL), ['https://www.jimms.fi/fi/Product/Show/123/gpu'])

    def test_missing_or_empty_listing_fails(self):
        for html in ('<h1>Blocked</h1>', '<div id="initproductlist"></div>'):
            with self.assertRaises(ValueError):
                parse_category(html, URL)


if __name__ == '__main__':
    unittest.main()
