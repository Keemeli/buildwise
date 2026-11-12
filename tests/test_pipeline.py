import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRAPER = ROOT / 'scraper'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class IntegrationTests(unittest.TestCase):
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

    def test_specs_excludes_jimms(self):
        from scraper.workers import specifications as specs
        with tempfile.TemporaryDirectory() as directory:
            for shop in ('Jimms', 'Datatronic'):
                (Path(directory) / f'{shop}.json').write_text(json.dumps({'shop': shop, 'category': 'gpu',
                    'items': [{'url': f'https://{shop.lower()}.fi/product'}]}))
            entries = specs.iter_listings(Path(directory), None)
            self.assertEqual([entry['shop'] for entry in entries], ['Datatronic'])

    def test_refresh_selects_requested_categories(self):
        from unittest.mock import patch
        from scraper.pipeline import refresh
        from scraper import cli as command
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(sys, 'argv', ['scraper', 'refresh', '--categories', 'gpu,cpu', '--skip-specs', '--data-dir', directory]), \
                 patch.object(refresh, 'PROJECT_ROOT', Path(directory)), \
                 patch.object(refresh, 'LOG_PATH', Path(directory) / 'refresh.jsonl'), \
                 patch.object(refresh, 'run_stage', return_value={'ok': True}) as stage:
                self.assertEqual(command.main(), 0)
                names = [call.args[0] for call in stage.call_args_list]
                self.assertEqual(names, ['datatronic-gpu', 'datatronic-cpu', 'normalise', 'export'])


if __name__ == '__main__':
    unittest.main()
