"""Proshop price extraction and explicit new-product scope from saved HTML."""
from pathlib import Path
from copy import deepcopy
import json
import unittest
from bs4 import BeautifulSoup
from scraper.retailers.proshop import ProshopAdapter
from scraper.retailers.contracts import UnsupportedCategoryError, UnsupportedOperationError

FIXTURES = Path(__file__).parent / 'fixtures/proshop'


class ProshopAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ProshopAdapter()
        self.url = self.adapter.category_url('gpu')

    def parse(self, html):
        return self.adapter.parse_category(html, 'gpu', self.url)

    def sample(self):
        soup = BeautifulSoup((FIXTURES / 'gpu_page_1.html').read_text(), 'html.parser')
        listing = soup.select_one('#products')
        for card in listing.select(':scope > li')[1:]:
            card.decompose()
        return soup

    def test_two_saved_pages_match_all_regular_prices_and_report_both_demo_ids(self):
        observed = json.loads((FIXTURES / 'observations.json').read_text())
        products, excluded = {}, []
        for page in observed['category_pages']:
            result = self.adapter.parse_category((FIXTURES / f"gpu_page_{page['page']}.html").read_text(),
                                                  'gpu', page['source_url'])
            self.assertEqual(result.site_total_products, 489)
            self.assertFalse(result.issues)
            self.assertFalse(result.product_requests)
            products.update({product.external_id: product.price_cents for product in result.observations})
            excluded.extend(item.external_id for item in result.exclusions)
            for item in page['items']:
                if item['observed_condition'] == 'not_marked_demo':
                    self.assertEqual(products[item['external_id']], item['price_cents'])
        self.assertEqual(len(products), 48)
        self.assertEqual(set(excluded), {'3203171d', '3482347d'})
        for product in observed['products']:
            self.assertEqual(products[product['external_id']], product['price_cents'])

    def test_pagination_and_unsupported_operations_are_explicit(self):
        self.assertEqual(self.adapter.page_url('gpu', 1), self.url)
        self.assertEqual(self.adapter.page_url('gpu', 2), self.url + '?pn=2')
        self.assertEqual(self.adapter.page_url('gpu', 3, category_url=self.url + '?pn=8'), self.url + '?pn=3')
        with self.assertRaises(UnsupportedCategoryError):
            self.adapter.category_url('cpu')
        with self.assertRaises(ValueError):
            self.adapter.page_url('gpu', 0)
        with self.assertRaises(UnsupportedOperationError):
            self.adapter.parse_product('', None)
        self.assertIn('gpu', self.adapter.specification_parser().field_map)

    def test_missing_invalid_and_conflicting_prices_stay_null_with_correct_reason(self):
        for price, reason in [(None, 'missing_price'), ('9,999 €', 'invalid_price'),
                               ('123 USD', 'invalid_price'), ('123,45', 'invalid_price')]:
            with self.subTest(price=price):
                soup = self.sample()
                amount = soup.select_one('.priceContainer .site-currency-lg')
                if price is None:
                    amount.decompose()
                else:
                    amount.string = price
                result = self.parse(str(soup))
                self.assertIsNone(result.observations[0].price_cents)
                self.assertEqual(result.issues[0].code, reason)
        soup = self.sample()
        amount = soup.select_one('.priceContainer .site-currency-lg')
        other = deepcopy(amount)
        other.string = '1,00 €'
        amount.insert_after(other)
        self.assertEqual(self.parse(str(soup)).issues[0].code, 'conflicting_price')

    def test_missing_identity_wrong_host_or_conflicting_id_are_not_saved(self):
        for mutation in ('name', 'id', 'host', 'mismatch'):
            with self.subTest(mutation=mutation):
                soup = self.sample()
                if mutation == 'name':
                    soup.select_one('h2').decompose()
                elif mutation == 'id':
                    soup.select_one('input[name=productId]').decompose()
                elif mutation == 'host':
                    soup.select_one('a.site-product-link')['href'] = 'https://other.example/3331069'
                else:
                    soup.select_one('input[name=productId]')['value'] = '999'
                result = self.parse(str(soup))
                self.assertEqual(result.observations, ())
                self.assertEqual(len(result.issues), 1)

    def test_duplicate_conflicts_and_demo_condition_cannot_become_regular_prices(self):
        soup = self.sample()
        first = soup.select_one('#products > li')
        duplicate = deepcopy(first)
        duplicate.select_one('.site-currency-lg').string = '1,00 €'
        first.insert_after(duplicate)
        result = self.parse(str(soup))
        self.assertEqual(len(result.observations), 1)
        self.assertIsNone(result.observations[0].price_cents)
        duplicate.select_one('h2').string = first.select_one('h2').get_text() + ' *DEMO*'
        result = self.parse(str(soup))
        self.assertEqual(result.observations, ())
        self.assertEqual(len(result.exclusions), 1)
        self.assertTrue(all(issue.code == 'duplicate_url' for issue in result.issues))

    def test_confirmed_empty_requires_listing_and_zero_published_total(self):
        with self.assertRaisesRegex(ValueError, 'missing Proshop'):
            self.parse('<div>unrelated page</div>')
        self.assertTrue(self.parse('<span id="product-count">0</span><ul id="products"></ul>').end_of_category)
        self.assertFalse(self.parse('<ul id="products"></ul>').end_of_category)


if __name__ == '__main__':
    unittest.main()
