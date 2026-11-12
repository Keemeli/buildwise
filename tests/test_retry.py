"""Focused explicit-retry checks using real adapters and offline cached HTML."""
import contextlib
from dataclasses import replace
from datetime import date
import hashlib
import fcntl
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scraper.cli import main
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from scraper.workers.collection_reporting import CollectionOutcome
from scraper.workers.pending_work import PendingWorkStore
from test_collection_policy_matrix import listing, product_page, product_url, response


class RetryTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.addCleanup(self.context.close)
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.context.enter_context(patch('requests.Session.get', side_effect=AssertionError('network forbidden')))
        self.root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        self.store = PendingWorkStore(self.root)

    def seed(self, adapter, *, kind='product', page=1, classification='retryable', number=123):
        source = adapter.page_url('gpu', page)
        url = source if kind == 'category' else product_url(adapter, number)
        outcome = CollectionOutcome('initial', adapter.config.name, 'category', 'gpu', url,
            source, 'missing_price', classification, 'missing', str(number),
            f'SKU-{number}' if adapter.config.key == 'jimms' else None)
        self.store.record(SimpleNamespace(shop=adapter.config.name, run_id='initial', finished_at='before'),
                          {(kind, 'gpu', url): outcome})
        return outcome

    def cache(self, adapter, url, html):
        path = self.root / 'raw/html' / adapter.config.key / date.today().isoformat() / (
            hashlib.sha256(url.encode()).hexdigest() + '.html')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(html)

    def retry(self, adapter, *args):
        return main(['retry', '--shop', adapter.config.key, '--data-dir', str(self.root), '--offline', *args])

    def entries(self):
        return list(json.loads(self.store.path.read_text())['entries'].values())

    def test_recovery_for_both_preserves_old_observations_and_records_resolution(self):
        for adapter in (JimmsAdapter(), DatatronicAdapter()):
            outcome = self.seed(adapter, page=2)
            url = outcome.url if adapter.config.capabilities.product_prices else outcome.source_url
            self.cache(adapter, url, product_page() if adapter.config.key == 'jimms' else listing(adapter))
            old = self.root / 'raw/previous.json'
            old.write_text('{"unchanged": true}')
            self.assertEqual(self.retry(adapter), 0)
            entry = next(e for e in self.entries() if e['shop'] == adapter.config.name)
            self.assertEqual(entry['status'], 'resolved')
            self.assertFalse(entry['retry_eligible'])
            self.assertEqual(entry['attempts'][0]['status'], 'resolved')
            self.assertEqual(entry['resolved_run_id'], entry['attempts'][0]['run_id'])
            self.assertEqual(old.read_text(), '{"unchanged": true}')
            if adapter.config.key == 'datatronic':
                docs = [json.loads(p.read_text()) for p in (self.root / 'raw').glob('datatronic_*.json')]
                self.assertEqual(docs[0]['page'], 2)
            self.assertEqual(self.retry(adapter), 0)
            self.assertEqual(len(next(e for e in self.entries() if e['shop'] == adapter.config.name)['attempts']), 1)

    def test_repeated_failure_retains_attempts_then_recovers(self):
        adapter = JimmsAdapter()
        outcome = self.seed(adapter)
        self.assertEqual(self.retry(adapter), 1)
        self.assertEqual(self.retry(adapter), 1)
        entry = self.entries()[0]
        self.assertEqual(len(entry['attempts']), 2)
        self.assertEqual(entry['latest_outcome']['reason'], 'offline_cache_missing')
        self.assertEqual(entry['status'], 'pending')
        self.cache(adapter, outcome.url, product_page())
        self.assertEqual(self.retry(adapter), 0)
        self.assertEqual(len(self.entries()[0]['attempts']), 3)
        self.assertEqual(self.entries()[0]['status'], 'resolved')

    def test_filters_classifications_shop_and_limit(self):
        adapter = JimmsAdapter()
        self.seed(adapter, classification='blocked')
        self.seed(adapter, classification='inspect', number=124)
        self.seed(adapter, classification='unavailable', number=125)
        self.seed(DatatronicAdapter())
        for number in (126, 127):
            outcome = self.seed(adapter, number=number)
            self.cache(adapter, outcome.url, product_page())
        self.assertEqual(self.retry(adapter, '--limit', '1'), 0)
        self.assertEqual(sum(len(e.get('attempts', [])) for e in self.entries()), 1)
        self.assertEqual(sum(e['status'] == 'resolved' for e in self.entries()), 1)

    def test_category_recovery_keeps_new_unresolved_product_and_exit_failure(self):
        adapter = DatatronicAdapter()
        outcome = self.seed(adapter, kind='category', page=2)
        self.cache(adapter, outcome.url, listing(adapter, price=None))
        self.assertEqual(self.retry(adapter), 1)
        category = next(e for e in self.entries() if e['kind'] == 'category')
        product = next(e for e in self.entries() if e['kind'] == 'product')
        self.assertEqual(category['status'], 'resolved')
        self.assertEqual(product['status'], 'pending')

    def test_missing_target_or_new_inspect_error_never_marks_resolved(self):
        adapter = DatatronicAdapter()
        outcome = self.seed(adapter)
        self.cache(adapter, outcome.source_url, listing(adapter, number=999))
        self.assertEqual(self.retry(adapter), 1)
        self.assertEqual(self.entries()[0]['status'], 'pending')
        adapter = JimmsAdapter()
        outcome = self.seed(adapter)
        self.cache(adapter, outcome.url, '<html>No product identity</html>')
        self.assertEqual(self.retry(adapter), 1)
        entry = next(e for e in self.entries() if e['shop'] == adapter.config.name)
        self.assertFalse(entry['retry_eligible'])
        self.assertEqual(entry['latest_outcome']['retry_classification'], 'inspect')
        self.assertEqual(self.retry(adapter), 0)
        self.assertEqual(len(next(e for e in self.entries() if e['shop'] == adapter.config.name)['attempts']), 1)

    def test_new_failure_reopens_resolved_entry_without_losing_history(self):
        adapter = JimmsAdapter()
        outcome = self.seed(adapter)
        self.cache(adapter, outcome.url, product_page())
        self.assertEqual(self.retry(adapter), 0)
        later = replace(outcome, run_id='later')
        self.store.record(SimpleNamespace(shop=adapter.config.name, run_id='later', finished_at='later'),
                          {('product', 'gpu', outcome.url): later})
        entry = self.entries()[0]
        self.assertEqual(entry['status'], 'pending')
        self.assertTrue(entry['retry_eligible'])
        self.assertNotIn('resolved_run_id', entry)
        self.assertEqual(len(entry['attempts']), 1)

    def test_concurrent_retry_command_is_rejected_before_attempt(self):
        adapter = JimmsAdapter()
        self.seed(adapter)
        with (self.store.path.parent / 'retry.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(SystemExit) as error:
                self.retry(adapter)
            self.assertEqual(error.exception.code, 2)
        self.assertEqual(self.entries()[0].get('attempts', []), [])

    def test_retry_respects_robots_and_reclassifies_blocked_work(self):
        adapter = JimmsAdapter()
        self.seed(adapter)
        def get(url, **kwargs):
            self.assertTrue(url.endswith('/robots.txt'))
            return response('User-agent: *\nDisallow: /\n', url)
        with patch('requests.Session.get', side_effect=get) as get_mock:
            code = main(['retry', '--shop', 'jimms', '--data-dir', str(self.root), '--force'])
        self.assertEqual(code, 1)
        self.assertEqual(get_mock.call_count, 1)
        entry = self.entries()[0]
        self.assertEqual(entry['latest_outcome']['retry_classification'], 'blocked')
        self.assertFalse(entry['retry_eligible'])
        self.assertEqual(entry['attempts'][0]['status'], 'unresolved')

    def test_http_failure_retains_retryable_attempt_and_counters(self):
        adapter = JimmsAdapter()
        outcome = self.seed(adapter)
        def get(url, **kwargs):
            return response('User-agent: *\nAllow: /\n', url) if url.endswith('/robots.txt') else response('', url, 429)
        with patch('requests.Session.get', side_effect=get), patch('scraper.common.fetching.time.sleep'):
            self.assertEqual(main(['retry', '--shop', 'jimms', '--data-dir', str(self.root), '--force']), 1)
        entry = self.entries()[0]
        self.assertEqual(entry['latest_outcome']['reason'], 'http_429')
        self.assertTrue(entry['retry_eligible'])
        report = json.loads((self.root / 'raw/scrape_runs.jsonl').read_text())
        self.assertEqual(report['counters']['network_responses'], 1)
        self.assertEqual(report['counters']['source_failures'], 1)
        self.assertEqual(report['counters']['unresolved_outcomes'], 1)
        self.assertEqual(entry['attempts'][0]['run_id'], report['run_id'])

    def test_retry_batch_shares_robots_delay_and_closes_session_once(self):
        adapter = JimmsAdapter()
        first = self.seed(adapter, number=123)
        second = self.seed(adapter, number=124)
        clock, calls = [0.0], []
        def get(url, **kwargs):
            calls.append((url, clock[0]))
            if url.endswith('/robots.txt'):
                return response('User-agent: *\nAllow: /\nCrawl-delay: 5\n', url)
            return response(product_page(), url) if url == first.url else response('', url, 429)
        def sleep(seconds):
            clock[0] += seconds
        with patch('requests.Session.get', side_effect=get), \
                patch('requests.Session.close') as close, \
                patch('scraper.common.fetching.time.monotonic', side_effect=lambda: clock[0]), \
                patch('scraper.common.fetching.time.sleep', side_effect=sleep):
            self.assertEqual(main(['retry', '--shop', 'jimms', '--data-dir', str(self.root), '--force']), 1)
        self.assertEqual([url for url, _ in calls[1:]], [first.url, second.url])
        self.assertEqual([when for _, when in calls], [0.0, 5.0, 10.0])
        close.assert_called_once()

    def test_datatronic_missing_and_invalid_prices_have_distinct_pending_policy(self):
        adapter = DatatronicAdapter()
        url = adapter.page_url('gpu', 1)
        for price, reason, eligible in ((None, 'missing_price', True),
                                        ('', 'missing_price', True),
                                        ('299,999 €', 'invalid_price', False)):
            with self.subTest(price=price):
                self.cache(adapter, url, listing(adapter, price=price))
                self.assertEqual(main(['collect', '--shop', 'datatronic', '--category', 'gpu',
                                       '--data-dir', str(self.root), '--offline']), 1)
                entry = self.entries()[0]
                self.assertEqual(entry['latest_outcome']['reason'], reason)
                self.assertEqual(entry['retry_eligible'], eligible)
                self.assertEqual(entry['latest_outcome']['retry_classification'],
                                 'retryable' if eligible else 'inspect')
                report = json.loads((self.root / 'raw/scrape_runs.jsonl').read_text().splitlines()[-1])
                self.assertEqual(report['counters']['null_price_observations'], 1)


if __name__ == '__main__':
    unittest.main()
