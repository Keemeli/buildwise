"""Shared specification commands, cache policy, preservation and normalisation."""
import contextlib
from dataclasses import replace
from datetime import date
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import requests

from scraper.cli import main
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from scraper.workers.specifications import SpecificationWorker, write_store
from test_collection_policy_matrix import response

GPU = Path(__file__).parent / 'fixtures/jimms/specifications/gpu_powercolor.html'


class SharedSpecificationTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.context.enter_context(patch('requests.Session.get', side_effect=AssertionError('live network forbidden')))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.raw, self.out = self.root / 'raw', self.root / 'out'
        self.raw.mkdir()

    def setup_shop(self, adapter, suffix=''):
        url = (f'https://datatronic.fi/gpu{suffix}' if adapter.config.key == 'datatronic'
               else f'https://www.jimms.fi/fi/Product/Show/123/gpu{suffix}')
        (self.raw / f'{adapter.config.key}{suffix}.json').write_text(json.dumps({
            'shop': adapter.config.name, 'category': 'gpu', 'fetched_at': '2023-11-14T22:13:20Z', 'items': [{
                'url': url, 'name': 'PowerColor Radeon RX 9070 XT 16GB GDDR6', 'price_cents': 29999,
                'external_id': '123', 'retailer_sku': 'SKU' if adapter.config.key == 'jimms' else None}]}))
        return url

    def html(self, adapter):
        return GPU.read_text() if adapter.config.key == 'jimms' else '<script>{"features":[{"name":"Tehonkulutus (maks.)","value":"180 W"}]}</script>'

    def cache(self, adapter, url, html, legacy=False):
        root = self.raw / 'html/specs' if legacy else self.raw / 'html'
        path = root / adapter.config.key / date.today().isoformat() / (hashlib.sha256(url.encode()).hexdigest() + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)
        os.utime(path, (1700000000, 1700000000))
        return path

    def run_shop(self, adapter, *args):
        return main(['specs', '--shop', adapter.config.key, '--category', 'gpu',
                     '--raw-dir', str(self.raw), '--out', str(self.out), *args])

    def items(self):
        return json.loads((self.out / 'specs.json').read_text())['items']

    def test_both_cli_commands_reuse_price_cache_and_normalise_shared_store(self):
        for adapter in (DatatronicAdapter(), JimmsAdapter()):
            url = self.setup_shop(adapter)
            self.cache(adapter, url, self.html(adapter))
            self.assertEqual(self.run_shop(adapter, '--offline'), 0)
            entry = self.items()[url]
            self.assertEqual(entry['fetched_at'], '2023-11-14T22:13:20+00:00')
            self.assertEqual(entry['origin'], 'cache')
            self.assertIsNone(entry['specs']['length_mm'])
            self.assertTrue((self.root / entry['raw_html']).exists())
        self.assertEqual(len(self.items()), 2)
        jimms = next(entry for entry in self.items().values() if entry['shop'] == 'Jimms')
        self.assertEqual(jimms['retailer_sku'], 'SKU')
        self.assertEqual(main(['normalise', '--raw-dir', str(self.raw), '--out', str(self.out)]), 0)
        component = json.loads((self.out / 'components.json').read_text())['components'][0]
        self.assertEqual(component['specs']['power_w'], 180)
        self.assertEqual(component['specs']['recommended_psu_w'], 800)
        self.assertEqual(component['spec_sources']['power_w'], 'parsed_product_page')
        self.assertEqual(self.run_shop(JimmsAdapter(), '--status'), 0)

    def test_failures_and_empty_pages_preserve_previous_success_and_other_shop(self):
        for adapter in (DatatronicAdapter(), JimmsAdapter()):
            url = self.setup_shop(adapter)
            self.cache(adapter, url, self.html(adapter))
            self.assertEqual(self.run_shop(adapter, '--offline'), 0)
        originals = self.items()
        for adapter in (DatatronicAdapter(), JimmsAdapter()):
            url = self.setup_shop(adapter)
            self.cache(adapter, url, '<h1>No supported data</h1>')
            self.assertEqual(self.run_shop(adapter, '--offline'), 1)
            entry = self.items()[url]
            self.assertEqual(entry['status'], 'ok')
            self.assertEqual(entry['specs'], originals[url]['specs'])
            self.assertEqual(entry['fetched_at'], originals[url]['fetched_at'])
            self.assertEqual(entry['last_attempt']['status'], 'empty')

    def test_robots_and_delays_apply_to_both_retailers(self):
        for adapter in (DatatronicAdapter(), JimmsAdapter()):
            url = self.setup_shop(adapter)
            other = self.setup_shop(adapter, '-2')
            clock, calls = [0.0], []
            def get(request_url, **kwargs):
                calls.append((request_url, clock[0]))
                if request_url.endswith('/robots.txt'):
                    return response('User-agent: *\nAllow: /\nCrawl-delay: 5\n', request_url)
                if request_url == other:
                    raise requests.Timeout('timeout')
                return response(self.html(adapter), request_url)
            def sleep(seconds):
                clock[0] += seconds
            with patch('requests.Session.get', side_effect=get), patch('scraper.common.fetching.time.sleep', side_effect=sleep), patch('scraper.common.fetching.time.monotonic', side_effect=lambda: clock[0]):
                self.assertEqual(self.run_shop(adapter, '--force'), 1)
            self.assertEqual([when for _, when in calls], [0, 5, 10])
            self.assertEqual(self.items()[url]['status'], 'ok')
            self.assertEqual(self.items()[other]['status'], 'failed')
            with patch('requests.Session.get', side_effect=lambda request_url, **kwargs: response('User-agent: *\nDisallow: /\n', request_url)) as get_mock:
                self.assertEqual(self.run_shop(adapter, '--force', '--limit', '1'), 1)
                self.assertEqual(get_mock.call_count, 1)

    def test_old_datatronic_cache_is_read_without_migration(self):
        adapter = DatatronicAdapter()
        url = self.setup_shop(adapter)
        cached = self.cache(adapter, url, self.html(adapter), legacy=True)
        original = cached.read_bytes()
        self.assertEqual(self.run_shop(adapter, '--offline'), 0)
        self.assertEqual(cached.read_bytes(), original)
        self.assertIn('html/specs/datatronic', self.items()[url]['raw_html'])

    def test_corrupt_store_and_failed_atomic_write_do_not_destroy_saved_data(self):
        self.out.mkdir()
        path = self.out / 'specs.json'
        path.write_text('corrupt')
        adapter = JimmsAdapter()
        self.setup_shop(adapter)
        with self.assertRaises(SystemExit):
            self.run_shop(adapter, '--offline')
        self.assertEqual(path.read_text(), 'corrupt')
        path.write_text('{"items": {"old": {"status": "ok"}}}')
        before = path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                write_store(path, {'items': {}})
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(list(self.out.glob('*.tmp')), [])

    def test_unsupported_specifications_are_rejected_before_session_creation(self):
        from argparse import Namespace
        adapter = JimmsAdapter()
        adapter.config = replace(adapter.config, capabilities=replace(adapter.config.capabilities, specifications=False))
        with patch('requests.Session') as session:
            with self.assertRaisesRegex(ValueError, 'does not support specifications'):
                SpecificationWorker(Namespace(), adapter)
            session.assert_not_called()

    def test_parser_failure_and_offline_miss_keep_previous_specs_for_both(self):
        from argparse import Namespace
        for adapter in (DatatronicAdapter(), JimmsAdapter()):
            url = self.setup_shop(adapter)
            cached = self.cache(adapter, url, self.html(adapter))
            self.assertEqual(self.run_shop(adapter, '--offline'), 0)
            values = self.items()[url]['specs']
            options = Namespace(raw_dir=self.raw, out=self.out, category=['gpu'], limit=None,
                                delay=1, force=False, reparse=True, status=False, checkpoint_every=1)
            session = Mock()
            worker = SpecificationWorker(options, adapter, session=session)
            with patch.object(worker.spec_parser, 'extract_features', side_effect=RuntimeError('broken parser')):
                self.assertEqual(worker.run(), 1)
            session.get.assert_not_called()
            session.close.assert_called_once()
            entry = self.items()[url]
            self.assertEqual(entry['specs'], values)
            self.assertEqual(entry['last_attempt']['status'], 'failed')
            self.assertIn('earlier specs retained', (self.out / 'specs_report.md').read_text())
            cached.unlink()
            self.assertEqual(self.run_shop(adapter, '--offline'), 1)
            self.assertEqual(self.items()[url], entry)


if __name__ == '__main__':
    unittest.main()
