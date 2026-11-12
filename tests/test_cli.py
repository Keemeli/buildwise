"""Unified command interface and offline end-to-end workflows."""
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.cli import main
from scraper.common.fetching import PageFetcher
from scraper.retailers.jimms import CATEGORY_URLS
from scraper.workers.jimms import page_url



class ManifestCollectionCLITests(unittest.TestCase):
    def test_offline_cli_output_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            url = 'https://www.jimms.fi/product'
            fetcher = PageFetcher(root / 'raw' / 'html', 'jimms', {'www.jimms.fi'})
            import hashlib
            fetcher.cache_dir.mkdir(parents=True)
            (fetcher.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.html')).write_text(
                '<h1>Example GPU</h1><meta property="product:price:amount" content="299.99">')
            fetcher.close()
            manifest = root / 'urls.json'
            manifest.write_text(json.dumps([{'category': 'gpu', 'url': url}]))
            result = subprocess.run([sys.executable, '-B', '-m', 'scraper', 'collect', '--shop', 'jimms',
                                     '--input', str(manifest), '--data-dir', str(root), '--offline'],
                                    cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(next((root / 'raw').glob('jimms_*.json')).read_text())
            self.assertEqual(payload['shop'], 'Jimms')
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            self.assertEqual(payload['origin'], 'cache')


class UnifiedCLITests(unittest.TestCase):
    def cache(self, root, shop, url, html):
        fetcher = PageFetcher(root / 'raw/html', shop, {'www.jimms.fi', 'datatronic.fi'})
        path = fetcher.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        fetcher.close()

    def test_jimms_category_collects_prices_in_one_offline_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            product = 'https://www.jimms.fi/fi/Product/Show/123/gpu'
            self.cache(root, 'jimms', page_url(CATEGORY_URLS['gpu'], 1),
                '<div id="initproductlist"><product-box><a href="' + product + '">GPU</a></product-box></div>')
            self.cache(root, 'jimms', product,
                '<h1>MSI RTX 5070</h1><meta property="product:price:amount" content="299.99">')
            with patch('requests.Session.get', side_effect=AssertionError('offline request')), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['collect', '--shop', 'jimms', '--category', 'gpu',
                                       '--offline', '--data-dir', str(root)]), 0)
            payload = json.loads(next((root / 'raw').glob('jimms_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)
            self.assertEqual(payload['origin'], 'cache')
            self.assertTrue((root / 'discovery/jimms_gpu.report.json').exists())

    def test_datatronic_collection_uses_same_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cache(root, 'datatronic', 'https://datatronic.fi/naytonohjaimet',
                '<div id="js-product-list"><article class="product-miniature">'
                '<h3 class="product-title"><a href="/gpu">MSI GPU</a></h3>'
                '<span class="price">299,99 €</span></article></div>')
            with patch('requests.Session.get', side_effect=AssertionError('offline request')), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['collect', '--shop', 'datatronic', '--category', 'gpu',
                                       '--offline', '--data-dir', str(root)]), 0)
            payload = json.loads(next((root / 'raw').glob('datatronic_*.json')).read_text())
            self.assertEqual(payload['items'][0]['price_cents'], 29999)

    def test_invalid_arguments_fail_before_worker_creation(self):
        for args in (["collect", "--shop", "jimms"],
                     ["collect", "--shop", "datatronic", "--input", "urls.json"],
                     ["collect", "--shop", "jimms", "--category", "gpu", "--pages", "0"],
                     ["collect", "--shop", "jimms", "--category", "gpu", "--delay", "nan"],
                     ["specs", "--shop", "datatronic", "--checkpoint-every", "0"]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), \
                 patch('requests.Session.get', side_effect=AssertionError('unexpected request')):
                with self.assertRaises(SystemExit) as exc:
                    main(args)
                self.assertEqual(exc.exception.code, 2)

    def test_export_check_needs_only_standard_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source.json'
            target = root / 'target.json'
            source.write_text('{"components": [], "component_count": 0}')
            target.write_text(source.read_text())
            result = subprocess.run([sys.executable, '-B', '-S', '-m', 'scraper', 'export', '--check',
                '--source', str(source), '--target', str(target)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_offline_refresh_runs_real_subcommands_and_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            (raw / 'jimms.json').write_text(json.dumps({'shop': 'Jimms', 'category': 'gpu',
                'fetched_at': '2026-11-05T12:00:00+00:00', 'items': [
                    {'name': 'MSI RTX 5070 12GB GDDR7', 'url': 'https://www.jimms.fi/product',
                     'price_cents': 29999}]}))
            target = root / 'web/components.json'
            result = subprocess.run([sys.executable, '-B', '-m', 'scraper', 'refresh', '--offline',
                '--data-dir', str(root), '--web-output', str(target)], cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(target.read_text()), json.loads((root / 'normalised/components.json').read_text()))
            record = json.loads((root / 'refresh_log.jsonl').read_text())
            self.assertEqual([stage['stage'] for stage in record['stages']], ['normalise', 'export'])


class CommandHelpTests(unittest.TestCase):
    def test_unified_commands_accept_help(self):
        for name in ('collect', 'specs', 'normalise', 'export', 'refresh'):
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, '-B', '-m', 'scraper', name, '--help'],
                                        cwd=ROOT, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('usage:', result.stdout)


if __name__ == '__main__':
    unittest.main()
