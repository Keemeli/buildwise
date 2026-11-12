"""Retailer contracts, registry, price parsers and parser configuration."""
import contextlib
import io
import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from scraper.common.raw_data import RawProduct
from scraper.config import NORMALISED_DIR, PROJECT_ROOT, RAW_DIR
from scraper.retailers.contracts import (
    CategoryResult, ProductRequest, RetailerAdapter, RetailerCapabilities, RetailerConfig,
    UnsupportedCategoryError, UnsupportedOperationError, listing_page_url,
)
from scraper.retailers.datatronic import DatatronicAdapter, DatatronicParser
from scraper.retailers.jimms import JimmsAdapter, JimmsParser, parse_category, parse_product
from scraper.retailers.proshop import ProshopAdapter
from scraper.retailers.registry import RetailerRegistry, default_registry

from tests.support import ROOT


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


JIMMS_FIXTURES = Path(__file__).resolve().parent / 'fixtures/jimms'


def jimms_card(price='<span class="price__amount">299,99 €</span>', sku='TEST-SKU'):
    return ('<div id="initproductlist"><product-box data-analytics=\'{"product":{"price":10}}\'>'
            '<h5 class="product-box-name"><a href="/fi/Product/Show/123/gpu">MSI GPU</a></h5>'
            f'<div class="product-box-sku">{sku}</div>{price}</product-box></div>')


class RetailerAdapterTests(unittest.TestCase):
    def test_page_parameter_replaces_old_value_and_retains_filters(self):
        url = JimmsAdapter().category_url('gpu')
        self.assertEqual(listing_page_url(url + '?page=5&sort=price#top', 2), url + '?sort=price&page=2')

    def test_registry_adapters_implement_contract_without_network(self):
        with patch('requests.Session.get', side_effect=AssertionError('unexpected network')):
            registry = default_registry()
            self.assertEqual(registry.keys, ('datatronic', 'jimms', 'proshop'))
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
        expected = json.loads((JIMMS_FIXTURES / 'expected_products.json').read_text())
        actual = []
        with patch('requests.Session.get', side_effect=AssertionError('unexpected network')):
            for page in (1, 2):
                result = adapter.parse_category((JIMMS_FIXTURES / f'gpu_page_{page}.html').read_text(),
                                                'gpu', adapter.page_url('gpu', page))
                self.assertEqual(len(result.observations), 25)
                self.assertEqual(result.product_requests, ())
                self.assertEqual(result.issues, ())
                self.assertIsNone(result.site_total_products)
                actual.extend({'page': page, 'name': item.name, 'price_cents': item.price_cents,
                               'url': item.url, 'external_id': item.external_id, 'retailer_sku': item.retailer_sku} for item in result.observations)
        self.assertEqual(actual, expected)
        self.assertEqual(len({item['url'] for item in actual}), 50)

    def test_jimms_uses_displayed_price_not_analytics(self):
        adapter = JimmsAdapter()
        result = adapter.parse_category(jimms_card(), 'gpu', adapter.page_url('gpu', 1))
        self.assertEqual(result.observations[0].price_cents, 29999)
        self.assertEqual(result.observations[0].external_id, '123')
        self.assertEqual(result.observations[0].retailer_sku, 'TEST-SKU')
        self.assertEqual(result.observations[0].extraction, 'category:.price__amount')

    def test_missing_invalid_or_conflicting_display_price_requests_follow_up(self):
        adapter = JimmsAdapter()
        for price, reason in [('', 'missing_price'), ('<span class="price__amount">unknown</span>', 'invalid_price'),
                              ('<span class="price__amount">10,00 €</span><span class="price__amount">20,00 €</span>', 'conflicting_price')]:
            with self.subTest(reason=reason):
                result = adapter.parse_category(jimms_card(price), 'gpu', adapter.page_url('gpu', 1))
                self.assertEqual(len(result.observations), 1)
                self.assertIsNone(result.observations[0].price_cents)
                self.assertEqual(result.observations[0].name, 'MSI GPU')
                self.assertEqual(result.observations[0].external_id, '123')
                self.assertEqual(result.observations[0].retailer_sku, 'TEST-SKU')
                self.assertEqual(result.issues[0].code, reason)
                self.assertEqual(result.product_requests, (ProductRequest('gpu', 'https://www.jimms.fi/fi/Product/Show/123/gpu', '123', reason, retailer_sku='TEST-SKU'),))

    def test_product_fallback_preserves_sku_and_returns_raw_product(self):
        request = ProductRequest('gpu', 'https://www.jimms.fi/fi/Product/Show/123/gpu', '123', retailer_sku='TEST-SKU')
        result = JimmsAdapter().parse_product('<h1>GPU</h1><meta property="product:price:amount" content="299.99">', request)
        self.assertIsInstance(result, RawProduct)
        self.assertEqual(result.price_cents, 29999)
        self.assertEqual(result.external_id, '123')
        self.assertEqual(result.retailer_sku, 'TEST-SKU')

    def test_adapter_rejects_foreign_source_and_product_urls(self):
        for adapter in (JimmsAdapter(), DatatronicAdapter()):
            with self.assertRaises(ValueError):
                adapter.parse_category('<html/>', 'gpu', 'https://other.example/list')
        with self.assertRaises(ValueError):
            JimmsAdapter().parse_product('<html/>', ProductRequest('gpu', 'https://other.example/gpu'))

    def test_jimms_missing_sku_does_not_erase_numeric_id(self):
        adapter = JimmsAdapter()
        result = adapter.parse_category(jimms_card(sku=''), 'gpu', adapter.page_url('gpu', 1))
        self.assertEqual(result.observations[0].external_id, '123')
        self.assertIsNone(result.observations[0].retailer_sku)

    def test_jimms_rejects_missing_or_conflicting_retailer_ids(self):
        adapter = JimmsAdapter()
        for url in ('https://www.jimms.fi/fi/Product/Show/gpu',
                    'https://www.jimms.fi/fi/Product/Show/123abc/gpu'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                adapter.product_id_from_url(url)
        with self.assertRaisesRegex(ValueError, 'conflicts'):
            adapter.parse_product('<html/>', ProductRequest('gpu', 'https://www.jimms.fi/fi/Product/Show/123/gpu', '456'))
        html = jimms_card().replace('/fi/Product/Show/123/gpu', '/fi/Product/Show/not-a-number/gpu')
        result = adapter.parse_category(html, 'gpu', adapter.page_url('gpu', 1))
        self.assertEqual(result.observations, ())
        self.assertEqual(result.issues[0].code, 'invalid_product_id')


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


class DatatronicParserTests(unittest.TestCase):
    def test_datatronic_listing_contract(self):
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


PROSHOP_FIXTURES = Path(__file__).parent / 'fixtures/proshop'


class ProshopAdapterTests(unittest.TestCase):
    def setUp(self):
        self.adapter = ProshopAdapter()
        self.url = self.adapter.category_url('gpu')

    def parse(self, html):
        return self.adapter.parse_category(html, 'gpu', self.url)

    def sample(self):
        soup = BeautifulSoup((PROSHOP_FIXTURES / 'gpu_page_1.html').read_text(), 'html.parser')
        listing = soup.select_one('#products')
        for card in listing.select(':scope > li')[1:]:
            card.decompose()
        return soup

    def test_two_saved_pages_match_all_regular_prices_and_report_both_demo_ids(self):
        observed = json.loads((PROSHOP_FIXTURES / 'observations.json').read_text())
        products, excluded = {}, []
        for page in observed['category_pages']:
            result = self.adapter.parse_category((PROSHOP_FIXTURES / f"gpu_page_{page['page']}.html").read_text(),
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


CONFIG_LISTING_HTML = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
                '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
                '<span class="price">299,99 €</span></article></div><p>Yhteensä 1 tuotetta</p>')


CONFIG_CATEGORY_HTML = ('<div id="initproductlist"><product-box>'
                 '<a href="/fi/Product/Show/123/gpu">GPU</a></product-box></div>')


CONFIG_PRODUCT_HTML = '<h1>MSI RTX 5070</h1><meta property="product:price:amount" content="299.99">'


class ProjectConfigurationTests(unittest.TestCase):
    def test_paths_resolve_to_project_not_worker_directory(self):
        self.assertEqual(PROJECT_ROOT, ROOT)
        self.assertEqual(RAW_DIR, ROOT / 'data/raw')
        self.assertEqual(NORMALISED_DIR, ROOT / 'data/normalised')


class ParserConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

    def test_parser_configuration_is_instance_local(self):
        custom = DatatronicParser('https://example.com')
        default = DatatronicParser()
        self.assertEqual(custom.parse_listing(CONFIG_LISTING_HTML)[0][0]['url'], 'https://example.com/gpu')
        self.assertEqual(default.parse_listing(CONFIG_LISTING_HTML)[0][0]['url'], 'https://datatronic.fi/gpu')
        self.assertEqual(JimmsParser().parse_product(CONFIG_PRODUCT_HTML), parse_product(CONFIG_PRODUCT_HTML))
        parser = JimmsParser({'example.com'})
        self.assertEqual(parser.parse_category(CONFIG_CATEGORY_HTML, 'https://example.com/list'),
                         ['https://example.com/fi/Product/Show/123/gpu'])


if __name__ == '__main__':
    unittest.main()
