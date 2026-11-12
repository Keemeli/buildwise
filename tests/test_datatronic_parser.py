"""Datatronic listing-card parsing."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))





class DatatronicParserTests(unittest.TestCase):
    def test_datatronic_listing_contract(self):
        sys.path.insert(0, str(ROOT))
        from scraper.retailers.datatronic import parse_listing
        items, total = parse_listing('<div id="js-product-list">'
            '<article class="product-miniature" data-id-product="42">'
            '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
            '<span class="price">1 234,56 €</span></article></div>'
            '<p>Yhteensä 1 tuotetta</p>')
        self.assertEqual(total, 1)
        self.assertEqual(items[0]['price_cents'], 123456)
        self.assertEqual(items[0]['external_id'], '42')
        self.assertEqual(items[0]['url'], 'https://datatronic.fi/gpu')


if __name__ == '__main__':
    unittest.main()
