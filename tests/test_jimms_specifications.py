"""Jimms specification parsing against saved markup and explicit unit fixtures."""
from pathlib import Path
import unittest
from scraper.retailers.jimms_specs import JimmsSpecParser

FIXTURES = Path(__file__).parent / 'fixtures/jimms/specifications'


class JimmsSpecificationTests(unittest.TestCase):
    def test_saved_gpu_descriptions_map_known_values_without_guessing_dimensions(self):
        parser = JimmsSpecParser()
        for name, memory, psu in [('gpu_powercolor.html', 16, 800), ('gpu_asrock.html', 10, 600), ('gpu_workstation.html', 96, None)]:
            with self.subTest(fixture=name):
                features, method = parser.extract_features((FIXTURES / name).read_text())
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
        features, _ = parser.extract_features((FIXTURES / 'cooler_misfiled_cpu.html').read_text())
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


if __name__ == '__main__':
    unittest.main()
