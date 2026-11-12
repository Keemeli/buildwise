"""Multi-retailer normalisation, parser configuration and price selection."""
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.pipeline.components import ComponentNameParser
from scraper.pipeline.normalisation import ComponentNormaliser



class MultiShopNormalisationTests(unittest.TestCase):
    def test_multiple_shops_and_intraday_price(self):
        with tempfile.TemporaryDirectory() as directory:
            raw = Path(directory) / 'raw'
            raw.mkdir()
            # Deliberately make the older record sort last by filename.
            for filename, shop, timestamp, price in [
                ('a.json', 'Jimms', '2026-11-05T12:00:00+00:00', 100),
                ('z.json', 'Jimms', '2026-11-05T09:00:00+00:00', 200),
                ('b.json', 'Datatronic', '2026-11-05T11:00:00+00:00', 300)]:
                (raw / filename).write_text(json.dumps({'shop': shop, 'category': 'gpu',
                    'fetched_at': timestamp, 'items': [{'name': 'MSI RTX 5070 12GB GDDR7',
                    'url': f'https://{shop.lower()}.fi/product', 'price_cents': price}]}))
            result = subprocess.run([sys.executable, '-m', 'scraper', 'normalise',
                '--raw-dir', str(raw), '--out', str(Path(directory) / 'out')], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            catalogue = json.loads((Path(directory) / 'out/components.json').read_text())
            self.assertEqual(catalogue['component_count'], 1)
            listings = catalogue['components'][0]['listings']
            self.assertEqual({x['shop']: x['price_cents'] for x in listings}, {'Jimms': 100, 'Datatronic': 300})
            self.assertIn('Jimms', catalogue['source'])


class NormaliserConfigurationTests(unittest.TestCase):
    def test_component_parser_configuration_does_not_change_default_parser(self):
        item = {'category': 'gpu', 'raw_name': 'MSI RTX 5070 12GB GDDR7',
                'shop': 'Jimms', 'url': 'https://www.jimms.fi/product',
                'external_id': None, 'price_cents': 29999,
                'fetched_at': '2026-11-05T12:00:00+00:00', 'snapshot_date': '2026-11-05'}
        custom = ComponentNameParser(parsers={'gpu': lambda name: {'custom': 42}},
                                     expected_fields={'gpu': ('custom',)})
        self.assertEqual(custom.parse(item)['specs'], {'custom': 42})
        self.assertEqual(ComponentNameParser().parse(item)['specs']['chipset'], 'RTX 5070')
        self.assertEqual(custom.parse(item)['missing_specs'], [])

    def test_normaliser_can_use_a_report_writer_without_replacing_parsing(self):
        class RecordingWriter:
            def write(self, out_dir, components, *args):
                self.components = components
                return out_dir / 'custom-report.md'

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            (raw / 'gpu.json').write_text(json.dumps({'shop': 'Jimms', 'category': 'gpu',
                'fetched_at': '2026-11-05T12:00:00+00:00', 'items': [
                    {'name': 'MSI RTX 5070 12GB GDDR7', 'url': 'https://www.jimms.fi/product',
                     'price_cents': 29999}]}))
            writer = RecordingWriter()
            worker = ComponentNormaliser(raw, root / 'out', report_writer=writer)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(worker.run(), 0)
            payload = json.loads((root / 'out/components.json').read_text())
            self.assertEqual(writer.components, payload['components'])
            self.assertEqual(payload['components'][0]['listings'][0]['shop'], 'Jimms')


if __name__ == '__main__':
    unittest.main()
