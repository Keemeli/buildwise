"""Retailer specification labels, units, ambiguity and saved HTML layouts."""
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from scraper.retailers.contracts import UnsupportedCategoryError
from scraper.retailers.jimms_specs import JimmsSpecParser
from scraper.retailers.proshop_specs import ProshopSpecParser


JIMMS_SPEC_FIXTURES = Path(__file__).parent / 'fixtures/jimms/specifications'


class JimmsSpecificationTests(unittest.TestCase):
    def test_saved_gpu_descriptions_map_known_values_without_guessing_dimensions(self):
        parser = JimmsSpecParser()
        for name, memory, psu in [('gpu_powercolor.html', 16, 800), ('gpu_asrock.html', 10, 600), ('gpu_workstation.html', 96, None)]:
            with self.subTest(fixture=name):
                features, method = parser.extract_features((JIMMS_SPEC_FIXTURES / name).read_text())
                specs, unmapped = parser.parse_specs('gpu', features)
                self.assertEqual(method, 'description_labels')
                self.assertEqual(specs['vram_gb'], memory)
                self.assertEqual(specs['memory_type'], 'GDDR7' if memory == 96 else 'GDDR6')
                if psu is None:
                    self.assertNotIn('recommended_psu_w', specs)
                    self.assertEqual(specs['power_w'], 600)
                else:
                    self.assertEqual(specs['recommended_psu_w'], psu)
                self.assertNotIn('length_mm', specs)
                self.assertIn('Koko' if memory == 96 else 'Mitat', unmapped)

    def test_cpu_labelled_cooler_does_not_generate_cpu_specs(self):
        parser = JimmsSpecParser()
        features, _ = parser.extract_features((JIMMS_SPEC_FIXTURES / 'cooler_misfiled_cpu.html').read_text())
        self.assertEqual(parser.parse_specs('cpu', features)[0], {})

    def test_structured_cpu_fields_use_common_units_and_keep_false(self):
        # A unit fixture for supported labels, not a captured CPU product page.
        html = '<div id="description"><dl><dt>Kanta</dt><dd>AM5</dd><dt>TDP</dt><dd>65 W</dd><dt>Perustaajuus</dt><dd>3,8 GHz</dd><dt>Jäähdytin sisältyy</dt><dd>Ei</dd></dl></div>'
        parser = JimmsSpecParser()
        features, _ = parser.extract_features(html)
        specs, _ = parser.parse_specs('cpu', features)
        self.assertEqual(specs, {'socket': 'AM5', 'tdp_w': 65, 'base_clock_mhz': 3800, 'cooler_included': False})

    def test_conflicting_aliases_remain_unknown_and_explicit_axes_are_supported(self):
        parser = JimmsSpecParser()
        specs, unmapped = parser.parse_specs('gpu', [('Mitat (PxLxK)', '288 x 132 x 56 mm'),
            ('Virtalähteen suosituskoko', '800 W'), ('Suositeltu virtalähteen koko', '600 W')])
        self.assertEqual(specs, {'length_mm': 288.0, 'width_mm': 132.0, 'height_mm': 56.0})
        self.assertIn('recommended_psu_w (conflicting values)', unmapped)

    def test_unrelated_page_and_marketing_before_technical_section_are_excluded(self):
        parser = JimmsSpecParser()
        self.assertEqual(parser.extract_features('<h1>GPU</h1><footer>Pituus: 300 mm</footer>')[0], [])
        features, _ = parser.extract_features('<div id="description"><p>Pituus: 999 mm</p><p><strong>Tekniset tiedot</strong>:</p><p>GPU: AMD RX 9070</p></div>')
        self.assertNotIn('length_mm', parser.parse_specs('gpu', features)[0])


PROSHOP_FIXTURES = Path(__file__).parent / 'fixtures/proshop'


class ProshopSpecificationTests(unittest.TestCase):
    def parse(self, pid):
        parser = ProshopSpecParser()
        features, method = parser.extract_features((PROSHOP_FIXTURES / f'product_{pid}.html').read_text())
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
        soup = BeautifulSoup((PROSHOP_FIXTURES / 'product_3331069.html').read_text(), 'html.parser')
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


if __name__ == '__main__':
    unittest.main()
