"""Shared specification collection, persistence, reports and compatibility."""
import argparse
import contextlib
import hashlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch

import requests

from scraper.cli import main
from scraper.common.raw_data import RawDataWriter, RawProduct
from scraper.pipeline.reports import SpecificationReportWriter
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from scraper.workers import specifications as specs
from scraper.workers.specifications import SpecificationWorker, write_store

from tests.support import response


class SpecificationWorkerTests(unittest.TestCase):
    def setUp(self):
        self.output = contextlib.ExitStack()
        self.output.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.output.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def tearDown(self):
        self.output.close()

    def test_specification_reparse_is_offline_and_keeps_output_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / 'raw'
            raw.mkdir()
            url = 'https://datatronic.fi/gpu'
            (raw / 'gpu.json').write_text(json.dumps({'shop': 'Datatronic', 'category': 'gpu',
                'items': [{'url': url, 'name': 'GPU', 'external_id': '42'}]}))
            opts = argparse.Namespace(raw_dir=raw, out=root / 'out', category=None, limit=None,
                delay=1, force=False, reparse=True, status=False, checkpoint_every=1)
            session = Mock()
            with patch.object(specs, 'CACHE_DIR', root / 'cache'):
                cached = specs.cache_path(url, '42', specs.date.today().isoformat())
                cached.parent.mkdir(parents=True)
                cached.write_text('<script>{"features": [{"name": "Tehonkulutus (maks.)", "value": "180 W"}]}</script>')
                self.assertEqual(specs.DatatronicSpecExtractor(opts, session=session).run(), 0)
            session.get.assert_not_called()
            session.close.assert_called_once()
            entry = json.loads((opts.out / 'specs.json').read_text())['items'][url]
            self.assertEqual(entry['status'], 'ok')
            self.assertEqual(entry['specs']['power_w'], 180)
            self.assertTrue((opts.out / 'specs_report.md').exists())


class SpecificationListingTests(unittest.TestCase):
    def test_specs_excludes_jimms(self):
        from scraper.workers import specifications as specs
        with tempfile.TemporaryDirectory() as directory:
            for shop in ('Jimms', 'Datatronic'):
                (Path(directory) / f'{shop}.json').write_text(json.dumps({'shop': shop, 'category': 'gpu',
                    'items': [{'url': f'https://{shop.lower()}.fi/product'}]}))
            entries = specs.iter_listings(Path(directory), None)
            self.assertEqual([entry['shop'] for entry in entries], ['Datatronic'])


class SpecificationFailureTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.raw = self.root / 'raw'
        self.raw.mkdir()
        self.context.enter_context(patch.object(specs, 'CACHE_DIR', self.root / 'cache'))
        self.context.enter_context(patch('scraper.common.fetching.time.monotonic', return_value=0))
        self.sleep = self.context.enter_context(patch('scraper.common.fetching.time.sleep'))

    def tearDown(self):
        self.context.close()

    def worker(self, urls, session, **updates):
        (self.raw / 'gpu.json').write_text(json.dumps({'shop': 'Datatronic', 'category': 'gpu',
            'items': [{'name': 'GPU', 'url': url} for url in urls]}))
        values = dict(raw_dir=self.raw, out=self.root / 'out', category=None, limit=None,
                      delay=1.0, force=False, reparse=False, status=False, checkpoint_every=1)
        values.update(updates)
        return specs.DatatronicSpecExtractor(argparse.Namespace(**values), session=session)

    def store(self):
        return json.loads((self.root / 'out/specs.json').read_text())['items']

    def test_request_failures_return_nonzero_and_are_throttled(self):
        session = Mock()
        session.get.side_effect = [response('', status=404), requests.Timeout('first'), requests.Timeout('second')]
        urls = ['https://datatronic.fi/gpu-1', 'https://datatronic.fi/gpu-2']
        self.assertEqual(self.worker(urls, session).run(), 1)
        self.assertEqual(session.get.call_args_list[0].args[0], 'https://datatronic.fi/robots.txt')
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(self.sleep.call_count, 2)
        self.assertTrue(all(call.args[0] >= 1 for call in self.sleep.call_args_list))
        self.assertTrue(all(item['status'] == 'failed' for item in self.store().values()))
        session.close.assert_called_once()

    def test_robots_disallow_prevents_product_request(self):
        session = Mock()
        session.get.return_value = response('User-agent: *\nDisallow: /gpu\n')
        url = 'https://datatronic.fi/gpu'
        self.assertEqual(self.worker([url], session).run(), 1)
        self.assertEqual(session.get.call_count, 1)
        self.assertIn('disallows', self.store()[url]['error'])

    def test_empty_page_is_not_success(self):
        session = Mock()
        session.get.side_effect = [response('', status=404), response('<h1>No data sheet</h1>')]
        url = 'https://datatronic.fi/gpu'
        self.assertEqual(self.worker([url], session).run(), 1)
        self.assertEqual(self.store()[url]['status'], 'empty')

    def test_partial_parse_keeps_success_and_reports_failure(self):
        session = Mock()
        html = '<script>{"features": [{"name": "Tehonkulutus (maks.)", "value": "180 W"}]}</script>'
        session.get.side_effect = [response('', status=404), response(html), requests.Timeout('timeout')]
        urls = ['https://datatronic.fi/gpu-1', 'https://datatronic.fi/gpu-2']
        self.assertEqual(self.worker(urls, session).run(), 1)
        self.assertEqual(self.store()[urls[0]]['specs']['power_w'], 180)
        self.assertEqual(self.store()[urls[1]]['status'], 'failed')
        self.assertTrue((self.root / 'out/specs_report.md').exists())

    def test_offline_missing_cache_reports_failure_without_requests(self):
        session = Mock()
        self.assertEqual(self.worker(['https://datatronic.fi/gpu'], session, reparse=True).run(), 1)
        session.get.assert_not_called()

    def test_cached_success_makes_no_requests(self):
        session = Mock()
        url = 'https://datatronic.fi/gpu'
        worker = self.worker([url], session)
        cached = specs.cache_path(url, '', specs.date.today().isoformat())
        cached.parent.mkdir(parents=True)
        cached.write_text('<script>{"features": [{"name": "Tehonkulutus (maks.)", "value": "180 W"}]}</script>')
        self.assertEqual(worker.run(), 0)
        session.get.assert_not_called()
        self.sleep.assert_not_called()
        self.assertEqual(self.store()[url]['specs']['power_w'], 180)

    def test_parser_exception_returns_failure_and_closes_session(self):
        session = Mock()
        session.get.side_effect = [response('', status=404), response('<h1>GPU</h1>')]
        worker = self.worker(['https://datatronic.fi/gpu'], session)
        worker.spec_parser = Mock()
        worker.spec_parser.extract_features.side_effect = ValueError('broken markup')
        self.assertEqual(worker.run(), 1)
        session.close.assert_called_once()
        self.assertIn('broken markup', self.store()['https://datatronic.fi/gpu']['error'])

    def test_offline_miss_preserves_previous_specs(self):
        session = Mock()
        url = 'https://datatronic.fi/gpu'
        worker = self.worker([url], session, reparse=True)
        previous = {'status': 'ok', 'specs': {'power_w': 180}, 'fetched_at': '2026-11-01T12:00:00+00:00'}
        worker.options.out.mkdir()
        (worker.options.out / 'specs.json').write_text(json.dumps({'items': {url: previous}}))
        self.assertEqual(worker.run(), 1)
        self.assertEqual(self.store()[url], previous)
        session.get.assert_not_called()

    def test_force_still_checks_robots_when_cache_exists(self):
        session = Mock()
        url = 'https://datatronic.fi/gpu'
        worker = self.worker([url], session, force=True)
        cached = specs.cache_path(url, '', specs.date.today().isoformat())
        cached.parent.mkdir(parents=True)
        cached.write_text('<h1>Old cached data</h1>')
        session.get.return_value = response('User-agent: *\nDisallow: /gpu\n')
        self.assertEqual(worker.run(), 1)
        self.assertEqual(session.get.call_count, 1)
        self.assertEqual(cached.read_text(), '<h1>Old cached data</h1>')


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
        catalogue = json.loads((self.out / 'components.json').read_text())
        self.assertEqual(catalogue['component_count'], 2)  # titles alone cannot share specs
        by_shop = {component['listings'][0]['shop']: component for component in catalogue['components']}
        self.assertEqual(by_shop['Datatronic']['specs']['power_w'], 180)
        self.assertEqual(by_shop['Jimms']['specs']['recommended_psu_w'], 800)
        self.assertEqual(by_shop['Datatronic']['spec_sources']['power_w'], 'parsed_product_page')
        self.assertNotIn('recommended_psu_w', by_shop['Datatronic']['specs'])
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


PROSHOP_FIXTURES = Path(__file__).parent / 'fixtures/proshop'


PROSHOP_PRODUCTS = json.loads((PROSHOP_FIXTURES / 'observations.json').read_text())['products']


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
        category_html = self.cache(category_url, (PROSHOP_FIXTURES / 'gpu_page_1.html').read_text())
        titles = {item['external_id']: item['name'] for item in
                  json.loads((PROSHOP_FIXTURES / 'observations.json').read_text())['category_pages'][0]['items']}
        RawDataWriter(self.root).write(shop='Proshop', category='gpu', source_type='category',
            source_url=category_url, raw_path=category_html, page=1, origin='cache',
            items=[RawProduct(titles[item['external_id']], item['price_cents'], item['source_url'],
                              external_id=item['external_id']) for item in PROSHOP_PRODUCTS])
        for product in PROSHOP_PRODUCTS:
            self.cache(product['source_url'], (PROSHOP_FIXTURES / f"product_{product['external_id']}.html").read_text())

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
        for product in PROSHOP_PRODUCTS:
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
        for product in PROSHOP_PRODUCTS:
            self.cache(product['source_url'], '<h1>Product without supported data sheet</h1>')
        self.assertEqual(self.run_specs(), 1)
        for product in PROSHOP_PRODUCTS:
            entry = self.store()['items'][product['source_url']]
            self.assertEqual(entry['specs'], previous[product['source_url']]['specs'])
            self.assertEqual(entry['status'], 'ok')
            self.assertEqual(entry['last_attempt']['status'], 'empty')
        self.assertIn('earlier specs retained', (self.out / 'specs_report.md').read_text())

    def test_server_card_unknown_psu_and_known_consumption_survive_normalisation(self):
        item = next(item for item in json.loads((PROSHOP_FIXTURES / 'observations.json').read_text())['category_pages'][0]['items']
                    if item['external_id'] == '3371545')
        category_url = 'https://www.proshop.fi/Naeytoenohjaimet'
        category_html = self.cache(category_url, (PROSHOP_FIXTURES / 'gpu_page_1.html').read_text())
        RawDataWriter(self.root).write(shop='Proshop', category='gpu', source_type='category',
            source_url=category_url, raw_path=category_html, page=1, origin='cache',
            items=[RawProduct(item['name'], item['price_cents'], item['url'], external_id='3371545')])
        self.cache(item['url'], (PROSHOP_FIXTURES / 'product_3371545.html').read_text())
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


class SpecificationReportTests(unittest.TestCase):
    def test_specification_report_uses_supplied_retailer_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            writer = SpecificationReportWriter({'gpu': {'custom_field': ['Custom label']}})
            store = {'items': {'url': {'category': 'gpu', 'status': 'ok',
                                      'specs': {'custom_field': 42}}}}
            report = writer.write(Path(directory), store).read_text()
            self.assertIn('custom_field', report)
            self.assertNotIn('recommended_psu_w', report)


if __name__ == '__main__':
    unittest.main()
