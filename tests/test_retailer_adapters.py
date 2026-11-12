"""Shared retailer configuration, result contract and adapter registry."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scraper.retailers.contracts import RetailerConfig, RetailerCapabilities, UnsupportedCategoryError
from scraper.retailers.registry import RetailerRegistry


from unittest.mock import patch
from scraper.common.raw_data import RawProduct
from scraper.retailers.contracts import CategoryResult, ProductRequest, RetailerAdapter, UnsupportedOperationError
from scraper.retailers.datatronic import DatatronicAdapter, DatatronicParser
from scraper.retailers.jimms import JimmsAdapter
from scraper.retailers.registry import default_registry
import json

class AdapterContractTests(unittest.TestCase):
    def config(self, paths):
        return RetailerConfig('sample', 'Sample', 'https://shop.example',
                              frozenset({'shop.example'}), paths, RetailerCapabilities(True, False))

    def test_configuration_copies_and_protects_category_paths(self):
        paths = {'gpu': '/graphics'}
        config = self.config(paths)
        paths['gpu'] = '/changed'
        self.assertEqual(config.category_url('gpu'), 'https://shop.example/graphics')
        with self.assertRaises(TypeError):
            config.category_paths['gpu'] = '/changed'
        with self.assertRaises(UnsupportedCategoryError):
            config.category_url('cpu')

    def test_category_paths_cannot_escape_the_retailer(self):
        for path in ('https://other.example/gpu', '//other.example/gpu', 'relative'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.config({'gpu': path})

    def test_registry_resolves_factories_and_rejects_unknown_keys(self):
        calls = []
        def factory():
            calls.append(True)
            return object()
        registry = RetailerRegistry({'sample': factory})
        registry.get(' SAMPLE ')
        self.assertEqual(calls, [True])
        self.assertEqual(registry.keys, ('sample',))
        with self.assertRaisesRegex(ValueError, 'unknown retailer'):
            registry.get('missing')

FIXTURES = Path(__file__).resolve().parent / 'fixtures/jimms'


def jimms_card(price='<span class="price__amount">299,99 €</span>', sku='TEST-SKU'):
    return ('<div id="initproductlist"><product-box data-analytics=\'{"product":{"price":10}}\'>'
            '<h5 class="product-box-name"><a href="/fi/Product/Show/123/gpu">MSI GPU</a></h5>'
            f'<div class="product-box-sku">{sku}</div>{price}</product-box></div>')


class RetailerAdapterTests(unittest.TestCase):
    def test_registry_adapters_implement_contract_without_network(self):
        with patch('requests.Session.get', side_effect=AssertionError('unexpected network')):
            registry = default_registry()
            self.assertEqual(registry.keys, ('datatronic', 'jimms'))
            for key in registry.keys:
                adapter = registry.get(key)
                self.assertIsInstance(adapter, RetailerAdapter)
                self.assertEqual(adapter.config.key, key)
                self.assertEqual(adapter.category_url('gpu'), adapter.config.category_url('gpu'))
                with self.assertRaises(UnsupportedCategoryError):
                    adapter.category_url('other')
                with self.assertRaises(ValueError):
                    adapter.page_url('gpu', 0)

    def test_pagination_preserves_each_existing_retailer_convention(self):
        datatronic, jimms = DatatronicAdapter(), JimmsAdapter()
        self.assertEqual(datatronic.page_url('gpu', 1), 'https://datatronic.fi/naytonohjaimet')
        self.assertEqual(datatronic.page_url('gpu', 2), 'https://datatronic.fi/naytonohjaimet?page=2')
        self.assertEqual(jimms.page_url('gpu', 1), jimms.category_url('gpu') + '?page=1')
        self.assertEqual(jimms.page_url('gpu', 2), jimms.category_url('gpu') + '?page=2')

    def test_datatronic_adapter_preserves_existing_parser_data_and_missing_price(self):
        html = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
                '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
                '<span class="price">299,99 €</span></article>'
                '<article class="product-miniature"><h3 class="product-title"><a href="/other">Other GPU</a></h3>'
                '</article></div><p>Yhteensä 100 tuotetta</p>')
        adapter = DatatronicAdapter()
        before, total = DatatronicParser().parse_listing(html)
        with patch('requests.Session.get', side_effect=AssertionError('unexpected network')):
            after = adapter.parse_category(html, 'gpu', adapter.page_url('gpu', 1))
        self.assertIsInstance(after, CategoryResult)
        self.assertEqual(after.observations, tuple(RawProduct.from_item(item, 'listing_card') for item in before))
        self.assertEqual(after.site_total_products, total)
        self.assertEqual(after.product_requests, ())
        self.assertEqual(after.issues[0].code, 'missing_price')
        self.assertFalse(adapter.config.capabilities.product_prices)
        with self.assertRaises(UnsupportedOperationError):
            adapter.parse_product('<html/>', ProductRequest('gpu', 'https://datatronic.fi/gpu'))

    def test_50_saved_jimms_prices_names_urls_and_skus_match(self):
        adapter = JimmsAdapter()
        expected = json.loads((FIXTURES / 'expected_products.json').read_text())
        actual = []
        with patch('requests.Session.get', side_effect=AssertionError('unexpected network')):
            for page in (1, 2):
                result = adapter.parse_category((FIXTURES / f'gpu_page_{page}.html').read_text(),
                                                'gpu', adapter.page_url('gpu', page))
                self.assertEqual(len(result.observations), 25)
                self.assertEqual(result.product_requests, ())
                self.assertEqual(result.issues, ())
                self.assertIsNone(result.site_total_products)
                actual.extend({'page': page, 'name': item.name, 'price_cents': item.price_cents,
                               'url': item.url, 'external_id': item.external_id} for item in result.observations)
        self.assertEqual(actual, expected)
        self.assertEqual(len({item['url'] for item in actual}), 50)

    def test_jimms_uses_displayed_price_not_analytics(self):
        adapter = JimmsAdapter()
        result = adapter.parse_category(jimms_card(), 'gpu', adapter.page_url('gpu', 1))
        self.assertEqual(result.observations[0].price_cents, 29999)
        self.assertEqual(result.observations[0].external_id, 'TEST-SKU')
        self.assertEqual(result.observations[0].extraction, 'category:.price__amount')

    def test_missing_invalid_or_conflicting_display_price_requests_follow_up(self):
        adapter = JimmsAdapter()
        for price, reason in [('', 'missing_price'), ('<span class="price__amount">unknown</span>', 'invalid_price'),
                              ('<span class="price__amount">10,00 €</span><span class="price__amount">20,00 €</span>', 'conflicting_price')]:
            with self.subTest(reason=reason):
                result = adapter.parse_category(jimms_card(price), 'gpu', adapter.page_url('gpu', 1))
                self.assertEqual(result.observations, ())
                self.assertEqual(result.issues[0].code, reason)
                self.assertEqual(result.product_requests, (ProductRequest('gpu', 'https://www.jimms.fi/fi/Product/Show/123/gpu', 'TEST-SKU', reason),))

    def test_product_fallback_preserves_sku_and_returns_raw_product(self):
        request = ProductRequest('gpu', 'https://www.jimms.fi/fi/Product/Show/123/gpu', 'TEST-SKU')
        result = JimmsAdapter().parse_product('<h1>GPU</h1><meta property="product:price:amount" content="299.99">', request)
        self.assertIsInstance(result, RawProduct)
        self.assertEqual(result.price_cents, 29999)
        self.assertEqual(result.external_id, 'TEST-SKU')

    def test_adapter_rejects_foreign_source_and_product_urls(self):
        for adapter in (JimmsAdapter(), DatatronicAdapter()):
            with self.assertRaises(ValueError):
                adapter.parse_category('<html/>', 'gpu', 'https://other.example/list')
        with self.assertRaises(ValueError):
            JimmsAdapter().parse_product('<html/>', ProductRequest('gpu', 'https://other.example/gpu'))


if __name__ == '__main__':
    unittest.main()
