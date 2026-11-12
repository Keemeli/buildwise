"""Proshop grouped GPU specifications and shared offline CLI integration."""
import contextlib
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bs4 import BeautifulSoup

from scraper.cli import main
from scraper.common.raw_data import RawDataWriter, RawProduct
from scraper.retailers.contracts import UnsupportedCategoryError
from scraper.retailers.proshop_specs import ProshopSpecParser

FIXTURES = Path(__file__).parent / 'fixtures/proshop'
PRODUCTS = json.loads((FIXTURES / 'observations.json').read_text())['products']


class ProshopSpecificationTests(unittest.TestCase):
    def parse(self, pid):
        parser = ProshopSpecParser()
        features, method = parser.extract_features((FIXTURES / f'product_{pid}.html').read_text())
        values, unmapped = parser.parse_specs('gpu', features)
        return values, unmapped, method

    def test_saved_products_extract_verified_units_and_keep_unsupported_fields_unknown(self):
        expected = {
            '3331069': (32, 512, 1000, 357.6, 76.0, 149.3),
            '3331106': (16, 256, 750, 304.0, 50.0, 126.0),
        }
        for pid, numbers in expected.items():
            with self.subTest(product=pid):
                values, _, method = self.parse(pid)
                self.assertEqual(method, 'grouped_specification_rows')
                self.assertEqual(len(values), 9)
                self.assertEqual(tuple(values[field] for field in (
                    'vram_gb', 'memory_bus_bit', 'recommended_psu_w', 'length_mm', 'width_mm', 'height_mm')), numbers)
                self.assertEqual(values['memory_type'], 'GDDR7')
                self.assertEqual(values['interface'], 'PCI Express 5.0')
                for field in ('power_w', 'slot_width', 'power_connectors'):
                    self.assertNotIn(field, values)

    def test_shipping_general_summary_and_accessories_do_not_supply_gpu_dimensions(self):
        soup = BeautifulSoup((FIXTURES / 'product_3331069.html').read_text(), 'html.parser')
        container = soup.select_one('#specItemsAccordion')
        for row in list(container.find_all(recursive=False)):
            label = row.select_one('.specItemTitle')
            if label is not None and label.get_text(strip=True) in {'Syvyys', 'Leveys', 'Korkeus'}:
                row.decompose()
        parser = ProshopSpecParser()
        features, _ = parser.extract_features(str(soup))
        values, _ = parser.parse_specs('gpu', features)
        self.assertTrue(all(field not in values for field in ('length_mm', 'width_mm', 'height_mm')))
        soup.select_one('#accordionPanel_specs').decompose()
        self.assertEqual(parser.extract_features(str(soup)), ([], 'none'))

    def test_conflicting_duplicate_values_are_reported_but_equivalent_units_agree(self):
        parser = ProshopSpecParser()
        values, unknown = parser.parse_specs('gpu', [
            ('Muisti/Koko', '32 Gt'), ('Muisti/Koko', '64 GB'),
            ('Muuta/Syvyys', '30.4 cm'), ('Muuta/Syvyys', '304 mm')])
        self.assertNotIn('vram_gb', values)
        self.assertEqual(values['length_mm'], 304.0)
        self.assertIn('vram_gb (conflicting values)', unknown)

    def test_unparsable_values_wrong_groups_and_unsupported_category_are_not_guessed(self):
        parser = ProshopSpecParser()
        values, unknown = parser.parse_specs('gpu', [
            ('Muuta/Syvyys', '30 - 40 cm'), ('Muisti/Koko', '16 / 32 Gt'),
            ('Muuta/Lähetyssyvyys', '42 cm'), ('Yleistä/Koko', '128 GB'),
            ('Muuta/Leveys', '0 mm'), ('Muisti/Koko', '0 Gt')])
        self.assertEqual(values, {})
        self.assertEqual(len(unknown), 6)
        with self.assertRaises(UnsupportedCategoryError):
            parser.parse_specs('cpu', [])

    def test_new_live_variants_match_saved_dimensions_and_operating_power(self):
        expected = {
            '3331067': (9, 348.0, 72.0, 146.0, 1000, None),
            '3395203': (9, 357.6, 76.0, 149.3, 1000, None),
            '3371545': (8, 266.7, None, 111.7, None, 600),
        }
        for pid, numbers in expected.items():
            with self.subTest(product=pid):
                values, _, _ = self.parse(pid)
                self.assertEqual((len(values), *(values.get(field) for field in (
                    'length_mm', 'width_mm', 'height_mm', 'recommended_psu_w', 'power_w'))), numbers)
        values, _ = ProshopSpecParser().parse_specs('gpu', [
            ('Järjestelmävaatimukset/Vaadittava virtalähde', '1000 W'),
            ('Muuta/Virran kulutus (toiminnassa)', '600 watti(a)')])
        self.assertEqual(values, {'recommended_psu_w': 1000, 'power_w': 600})


class ProshopSpecificationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.context.enter_context(patch('requests.Session.get', side_effect=AssertionError('live request forbidden')))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.raw, self.out = self.root / 'raw', self.root / 'normalised'
        category_url = 'https://www.proshop.fi/Naeytoenohjaimet'
        category_html = self.cache(category_url, (FIXTURES / 'gpu_page_1.html').read_text())
        titles = {item['external_id']: item['name'] for item in
                  json.loads((FIXTURES / 'observations.json').read_text())['category_pages'][0]['items']}
        RawDataWriter(self.root).write(shop='Proshop', category='gpu', source_type='category',
            source_url=category_url, raw_path=category_html, page=1, origin='cache',
            items=[RawProduct(titles[item['external_id']], item['price_cents'], item['source_url'],
                              external_id=item['external_id']) for item in PRODUCTS])
        for product in PRODUCTS:
            self.cache(product['source_url'], (FIXTURES / f"product_{product['external_id']}.html").read_text())

    def cache(self, url, html):
        path = self.raw / 'html/proshop' / date.today().isoformat() / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        os.utime(path, (1700000000, 1700000000))
        return path

    def run_specs(self):
        return main(['specs', '--shop', 'proshop', '--category', 'gpu', '--limit', '2',
                     '--raw-dir', str(self.raw), '--out', str(self.out), '--offline'])

    def store(self):
        return json.loads((self.out / 'specs.json').read_text())

    def test_shared_cli_preserves_identifiers_other_shops_and_normaliser_compatibility(self):
        self.out.mkdir()
        existing = {'shop': 'Jimms', 'category': 'gpu', 'status': 'ok', 'specs': {'power_w': 180}}
        (self.out / 'specs.json').write_text(json.dumps({'items': {'https://www.jimms.fi/product': existing}}))
        before = {path: path.read_bytes() for path in self.raw.glob('*.json')}
        self.assertEqual(self.run_specs(), 0)
        items = self.store()['items']
        self.assertEqual(items['https://www.jimms.fi/product'], existing)
        for product in PRODUCTS:
            entry = items[product['source_url']]
            self.assertEqual((entry['status'], entry['spec_count']), ('ok', 9))
            self.assertEqual(entry['external_id'], product['external_id'])
            self.assertEqual(entry['fetched_at'], '2023-11-14T22:13:20+00:00')
            self.assertEqual(entry['extraction'], 'grouped_specification_rows')
            self.assertTrue((self.root / entry['raw_html']).is_file())
            self.assertIsNone(entry['specs']['power_w'])
        self.assertEqual(main(['normalise', '--raw-dir', str(self.raw), '--out', str(self.out)]), 0)
        catalogue = json.loads((self.out / 'components.json').read_text())
        self.assertEqual(catalogue['component_count'], 2)
        for component in catalogue['components']:
            self.assertIn(component['specs']['length_mm'], (357.6, 304.0))
            self.assertEqual(component['spec_sources']['length_mm'], 'parsed_product_page')
        self.assertEqual({path: path.read_bytes() for path in self.raw.glob('*.json')}, before)

    def test_empty_data_sheet_returns_failure_and_preserves_previous_success(self):
        self.assertEqual(self.run_specs(), 0)
        previous = self.store()['items']
        for product in PRODUCTS:
            self.cache(product['source_url'], '<h1>Product without supported data sheet</h1>')
        self.assertEqual(self.run_specs(), 1)
        for product in PRODUCTS:
            entry = self.store()['items'][product['source_url']]
            self.assertEqual(entry['specs'], previous[product['source_url']]['specs'])
            self.assertEqual(entry['status'], 'ok')
            self.assertEqual(entry['last_attempt']['status'], 'empty')
        self.assertIn('earlier specs retained', (self.out / 'specs_report.md').read_text())

    def test_server_card_unknown_psu_and_known_consumption_survive_normalisation(self):
        item = next(item for item in json.loads((FIXTURES / 'observations.json').read_text())['category_pages'][0]['items']
                    if item['external_id'] == '3371545')
        category_url = 'https://www.proshop.fi/Naeytoenohjaimet'
        category_html = self.cache(category_url, (FIXTURES / 'gpu_page_1.html').read_text())
        RawDataWriter(self.root).write(shop='Proshop', category='gpu', source_type='category',
            source_url=category_url, raw_path=category_html, page=1, origin='cache',
            items=[RawProduct(item['name'], item['price_cents'], item['url'], external_id='3371545')])
        self.cache(item['url'], (FIXTURES / 'product_3371545.html').read_text())
        self.assertEqual(main(['specs', '--shop', 'proshop', '--category', 'gpu', '--limit', '3',
                              '--raw-dir', str(self.raw), '--out', str(self.out), '--offline']), 0)
        entry = self.store()['items'][item['url']]
        self.assertEqual((entry['spec_count'], entry['specs']['power_w']), (8, 600))
        self.assertIsNone(entry['specs']['recommended_psu_w'])
        self.assertIsNone(entry['specs']['width_mm'])
        self.assertEqual(main(['normalise', '--raw-dir', str(self.raw), '--out', str(self.out)]), 0)
        component = next(component for component in json.loads((self.out / 'components.json').read_text())['components']
                         if any(listing['url'] == item['url'] for listing in component['listings']))
        self.assertEqual(component['specs']['power_w'], 600)
        self.assertEqual(component['specs']['length_mm'], 266.7)


if __name__ == '__main__':
    unittest.main()
