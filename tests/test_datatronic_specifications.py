"""Datatronic specification filtering, parsing and request/failure policy."""
import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scraper.workers import specifications as specs


def response(text, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = text.encode('utf-8')
    result.encoding = 'utf-8'
    return result


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
        session.get.side_effect = [response('', 404), requests.Timeout('first'), requests.Timeout('second')]
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
        session.get.side_effect = [response('', 404), response('<h1>No data sheet</h1>')]
        url = 'https://datatronic.fi/gpu'
        self.assertEqual(self.worker([url], session).run(), 1)
        self.assertEqual(self.store()[url]['status'], 'empty')

    def test_partial_parse_keeps_success_and_reports_failure(self):
        session = Mock()
        html = '<script>{"features": [{"name": "Tehonkulutus (maks.)", "value": "180 W"}]}</script>'
        session.get.side_effect = [response('', 404), response(html), requests.Timeout('timeout')]
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
        session.get.side_effect = [response('', 404), response('<h1>GPU</h1>')]
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


if __name__ == '__main__':
    unittest.main()
