"""Project paths and isolated parser configuration."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.config import PROJECT_ROOT, RAW_DIR, NORMALISED_DIR
from scraper.retailers.datatronic import DatatronicParser
from scraper.retailers.jimms import JimmsParser, parse_product

LISTING_HTML = ('<div id="js-product-list"><article class="product-miniature" data-id-product="42">'
                '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
                '<span class="price">299,99 €</span></article></div><p>Yhteensä 1 tuotetta</p>')

CATEGORY_HTML = ('<div id="initproductlist"><product-box>'
                 '<a href="/fi/Product/Show/123/gpu">GPU</a></product-box></div>')

PRODUCT_HTML = '<h1>MSI RTX 5070</h1><meta property="product:price:amount" content="299.99">'


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
        self.assertEqual(custom.parse_listing(LISTING_HTML)[0][0]['url'], 'https://example.com/gpu')
        self.assertEqual(default.parse_listing(LISTING_HTML)[0][0]['url'], 'https://datatronic.fi/gpu')
        self.assertEqual(JimmsParser().parse_product(PRODUCT_HTML), parse_product(PRODUCT_HTML))
        parser = JimmsParser({'example.com'})
        self.assertEqual(parser.parse_category(CATEGORY_HTML, 'https://example.com/list'),
                         ['https://example.com/fi/Product/Show/123/gpu'])


if __name__ == '__main__':
    unittest.main()
