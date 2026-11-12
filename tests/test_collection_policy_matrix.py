"""Checkpoint 3: agreed collection policy against both real retailer adapters."""
import contextlib
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scraper.common.fetching import PageFetcher
from scraper.common.raw_data import RawDataWriter
from scraper.retailers.contracts import ProductRequest, UnsupportedOperationError
from scraper.retailers.datatronic import DatatronicAdapter
from scraper.retailers.jimms import JimmsAdapter
from scraper.workers.collection_worker import CollectionWorker
from scraper.workers.collection_reporting import classify_problem

ADAPTERS = (DatatronicAdapter, JimmsAdapter)
OBSERVED = 1700000000


def product_url(adapter, number=123):
    return (f'https://datatronic.fi/gpu-{number}' if adapter.config.key == 'datatronic'
            else f'https://www.jimms.fi/fi/Product/Show/{number}/gpu')


def card(adapter, price='299,99 €', number=123):
    url = product_url(adapter, number)
    if adapter.config.key == 'datatronic':
        amount = f'<span class="price">{price}</span>' if price is not None else ''
        return (f'<article class="product-miniature" data-id-product="{number}">'
                f'<h3 class="product-title"><a href="{url}">MSI RTX 5070 12GB GDDR7</a></h3>{amount}</article>')
    amount = f'<span class="price__amount">{price}</span>' if price is not None else ''
    return (f'<product-box><h5 class="product-box-name"><a href="{url}">MSI RTX 5070 12GB GDDR7</a></h5>'
            f'<div class="product-box-sku">SKU-{number}</div>{amount}</product-box>')


def listing(adapter, price='299,99 €', number=123, extra='', total=100):
    identity = 'js-product-list' if adapter.config.key == 'datatronic' else 'initproductlist'
    return f'<div id="{identity}">{card(adapter, price, number)}{extra}</div><p>Yhteensä {total} tuotetta</p>'


def product_page(price='299.99'):
    metadata = f'<meta property="product:price:amount" content="{price}">' if price is not None else ''
    return '<h1>MSI RTX 5070 12GB GDDR7</h1>' + metadata


def response(text, url, status=200):
    item = requests.Response()
    item.status_code, item.url, item.encoding = status, url, 'utf-8'
    item._content = text.encode('utf-8')
    return item


class CollectionPolicyMatrixTests(unittest.TestCase):
    def setUp(self):
        self.context = contextlib.ExitStack()
        self.context.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.context.enter_context(contextlib.redirect_stderr(io.StringIO()))
        self.context.enter_context(patch('scraper.common.fetching.time.sleep'))
        self.context.enter_context(patch('scraper.common.fetching.time.monotonic', return_value=0))

    def tearDown(self):
        self.context.close()

    def run_case(self, adapter, sources, *, cached=None, offline=False, pages=1,
                 categories=('gpu',), robots='User-agent: *\nAllow: /\n', writer=None, product_requests=()):
        root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
        session = Mock()
        calls = []
        def get(url, **kwargs):
            calls.append(url)
            if offline:
                raise AssertionError('offline collection attempted a network request')
            if url.endswith('/robots.txt'):
                if isinstance(robots, Exception):
                    raise robots
                return response(robots, url) if isinstance(robots, str) else robots
            value = sources[url]
            if isinstance(value, Exception):
                raise value
            return response(value, url) if isinstance(value, str) else value
        session.get.side_effect = get
        fetcher = PageFetcher(root / 'raw/html', adapter.config.key,
                              set(adapter.config.allowed_hosts), offline=offline, session=session)
        for url in cached or ():
            path = fetcher.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.html')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sources[url])
            os.utime(path, (OBSERVED, OBSERVED))
        raw_writer = writer(root) if writer else None
        originals = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'raw').glob('*.json')}
        result = CollectionWorker(adapter, root, fetcher, categories, pages, raw_writer=raw_writer,
                                  product_requests=product_requests).run()
        for path, digest in originals.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        documents = [json.loads(p.read_text()) for p in (root / 'raw').glob('*.json') if p not in originals]
        record = json.loads((root / 'raw/scrape_runs.jsonl').read_text())
        session.close.assert_called_once()
        self.assertEqual(record['run_id'], result.run_id)
        self.assertEqual(record['status'], result.status)
        self.assertEqual(record['exit_code'], result.exit_code)
        self.assertEqual(record['counters']['unresolved_outcomes'], len(record['failures']))
        self.assertEqual(record['counters']['recovered_issues'], len(record['recovered']))
        self.assertEqual(result.counters.observations_saved, sum(len(d['items']) for d in documents))
        self.assertEqual(result.counters.observations_saved,
                         result.counters.priced_observations + result.counters.null_price_observations)
        for document in documents:
            self.assertEqual(document['run_id'], result.run_id)
            self.assertTrue((root / document['raw_html']).is_file())
        for outcome in (*result.failures, *result.recovered):
            self.assertEqual(outcome.run_id, result.run_id)
            self.assertEqual(outcome.shop, adapter.config.name)
            self.assertTrue(outcome.category and outcome.stage and outcome.url and outcome.source_url)
            self.assertIn(outcome.retry_classification, ('retryable', 'inspect', 'blocked', 'unavailable'))
        return result, documents, calls, root

    def test_success_cache_and_network_counters_for_both_retailers(self):
        for factory in ADAPTERS:
            for offline in (False, True):
                with self.subTest(retailer=factory.__name__, offline=offline):
                    adapter = factory()
                    url = adapter.page_url('gpu', 1)
                    result, docs, calls, _ = self.run_case(adapter, {url: listing(adapter)},
                                                         cached=(url,) if offline else (), offline=offline)
                    self.assertEqual((result.status, result.exit_code, result.items_found), ('ok', 0, 1))
                    self.assertEqual((result.counters.category_pages_planned, result.counters.category_pages_attempted,
                                      result.counters.category_pages_processed), (1, 1, 1))
                    self.assertEqual((result.counters.cache_hits, result.counters.network_responses), (int(offline), int(not offline)))
                    self.assertEqual((result.counters.source_failures, result.counters.source_responses), (0, 1))
                    self.assertEqual(result.coverage[0]['reason'], 'page_limit')
                    self.assertEqual(len(calls), 0 if offline else 2)  # robots is not a source response
                    self.assertEqual(docs[0]['items'][0]['external_id'], '123')
                    if offline:
                        self.assertEqual(docs[0]['fetched_at'], '2023-11-14T22:13:20+00:00')

    def test_all_null_prices_are_partial_and_retained_for_both_retailers(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                url = adapter.page_url('gpu', 1)
                sources = {url: listing(adapter, None)}
                if adapter.config.capabilities.product_prices:
                    sources[product_url(adapter)] = product_page(None)
                result, docs, _, _ = self.run_case(adapter, sources)
                self.assertEqual((result.status, result.exit_code, result.items_found), ('partial', 1, 1))
                self.assertEqual((result.counters.priced_observations, result.counters.null_price_observations), (0, 1))
                self.assertEqual(len(result.failures), 1)
                self.assertEqual(result.failures[0].reason, 'missing_price')
                self.assertEqual(result.failures[0].retry_classification, 'retryable')
                self.assertIsNone(docs[0]['items'][0]['price_cents'])
                self.assertEqual(docs[0]['items'][0]['external_id'], '123')

    def test_jimms_fallback_recovery_has_one_recovered_work_item(self):
        adapter = JimmsAdapter()
        sources = {adapter.page_url('gpu', 1): listing(adapter, None), product_url(adapter): product_page()}
        result, docs, _, _ = self.run_case(adapter, sources)
        self.assertEqual((result.status, result.exit_code, len(result.failures)), ('ok', 0, 0))
        self.assertEqual((result.counters.recovered_issues, result.counters.product_followups_attempted), (1, 1))
        self.assertEqual((result.counters.observations_saved, result.counters.null_price_observations), (1, 0))
        self.assertEqual(docs[0]['source_type'], 'product')
        self.assertEqual(docs[0]['items'][0]['retailer_sku'], 'SKU-123')

    def test_jimms_failed_fallback_classifications_and_null_source_are_preserved(self):
        adapter = JimmsAdapter()
        for status, classification in [(429, 'retryable'), (503, 'retryable'), (404, 'unavailable'), (410, 'unavailable')]:
            with self.subTest(status=status):
                source = adapter.page_url('gpu', 1)
                sources = {source: listing(adapter, None), product_url(adapter): response('', product_url(adapter), status)}
                result, docs, _, _ = self.run_case(adapter, sources)
                self.assertEqual((result.status, result.exit_code, len(result.failures)), ('partial', 1, 1))
                self.assertEqual(result.failures[0].retry_classification, classification)
                self.assertEqual((result.failures[0].external_id, result.failures[0].retailer_sku), ('123', 'SKU-123'))
                self.assertEqual((result.counters.source_failures, result.counters.network_responses), (1, 2))
                self.assertEqual(docs[0]['source_url'], source)
                self.assertEqual(docs[0]['source_type'], 'category')
                self.assertIsNone(docs[0]['items'][0]['price_cents'])

    def test_offline_misses_are_retryable_and_never_use_network_for_both(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                result, docs, calls, _ = self.run_case(adapter, {}, offline=True)
                self.assertEqual((result.status, result.exit_code, result.items_found), ('failed', 1, 0))
                self.assertEqual(result.failures[0].reason, 'offline_cache_missing')
                self.assertEqual(result.failures[0].retry_classification, 'retryable')
                self.assertEqual((result.counters.source_failures, result.counters.source_responses), (1, 0))
                self.assertEqual((docs, calls), ([], []))

    def test_robots_disallow_blocks_source_requests_for_both(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                result, docs, calls, _ = self.run_case(factory(), {}, robots='User-agent: *\nDisallow: /\n')
                self.assertEqual((result.status, result.exit_code), ('failed', 1))
                self.assertEqual(result.failures[0].reason, 'robots_disallowed')
                self.assertEqual(result.failures[0].retry_classification, 'blocked')
                self.assertEqual(result.counters.network_responses, 0)
                self.assertEqual(len(calls), 1)
                self.assertEqual(docs, [])

    def test_repeated_pages_preserve_success_and_stop_category_for_both(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                sources = {adapter.page_url('gpu', p): listing(adapter) for p in (1, 2)}
                result, docs, calls, _ = self.run_case(adapter, sources, pages=3)
                self.assertEqual((result.status, result.exit_code, result.items_found), ('partial', 1, 1))
                self.assertEqual((result.counters.category_pages_planned, result.counters.category_pages_processed), (3, 1))
                self.assertEqual(result.failures[0].reason, 'repeated_page')
                self.assertEqual(result.failures[0].retry_classification, 'inspect')
                self.assertEqual(len(docs), 1)
                self.assertNotIn(adapter.page_url('gpu', 3), calls)

    def test_empty_without_evidence_is_unresolved_for_both(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                container = 'js-product-list' if adapter.config.key == 'datatronic' else 'initproductlist'
                result, docs, _, _ = self.run_case(adapter, {adapter.page_url('gpu', 1): f'<div id="{container}"></div>'})
                self.assertEqual((result.status, result.exit_code), ('failed', 1))
                self.assertEqual(result.failures[0].retry_classification, 'inspect')
                self.assertEqual(result.coverage[0]['reason'], 'unresolved')
                self.assertEqual(docs, [])

    def test_datatronic_confirmed_empty_total_is_success(self):
        adapter = DatatronicAdapter()
        result, docs, calls, _ = self.run_case(adapter, {adapter.page_url('gpu', 1):
            '<div id="js-product-list"></div><p>Yhteensä 0 tuotetta</p>'}, pages=3)
        self.assertEqual((result.status, result.exit_code), ('ok', 0))
        self.assertEqual(result.counters.category_pages_attempted, 1)
        self.assertEqual(result.coverage[0]['reason'], 'confirmed_end')
        self.assertEqual(docs, [])

    def test_partial_category_failure_continues_other_category_for_both(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                sources = {adapter.page_url('gpu', 1): requests.Timeout('timeout'),
                           adapter.page_url('cpu', 1): listing(adapter)}
                result, docs, _, _ = self.run_case(adapter, sources, categories=('gpu', 'cpu'))
                self.assertEqual((result.status, result.exit_code, result.items_found), ('partial', 1, 1))
                self.assertEqual(result.counters.category_pages_attempted, 2)
                self.assertEqual(result.failures[0].retry_classification, 'retryable')
                self.assertEqual(docs[0]['category'], 'cpu')

    def test_same_unresolved_product_across_categories_has_one_outcome(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                sources = {adapter.page_url(category, 1): listing(adapter, None) for category in ('gpu', 'cpu')}
                if adapter.config.capabilities.product_prices:
                    sources[product_url(adapter)] = product_page(None)
                result, docs, _, _ = self.run_case(adapter, sources, categories=('gpu', 'cpu'))
                self.assertEqual((result.items_found, result.counters.unique_products_identified), (1, 1))
                self.assertEqual(result.counters.null_price_observations, 1)
                self.assertEqual(len(result.failures), 1)

    def test_missing_listing_container_cannot_parse_unrelated_featured_products(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                result, docs, _, _ = self.run_case(adapter, {adapter.page_url('gpu', 1): card(adapter)})
                self.assertEqual((result.status, result.exit_code), ('failed', 1))
                self.assertEqual(result.failures[0].retry_classification, 'inspect')
                self.assertEqual(docs, [])

    def test_unidentified_card_marks_partial_without_losing_valid_products(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                broken = ('<article class="product-miniature"><span class="price">100,00 €</span></article>'
                          if adapter.config.key == 'datatronic' else '<product-box><span class="price__amount">100,00 €</span></product-box>')
                result, docs, _, _ = self.run_case(adapter, {adapter.page_url('gpu', 1): listing(adapter, extra=broken)})
                self.assertEqual((result.status, result.exit_code, result.items_found), ('partial', 1, 1))
                self.assertEqual(len(result.failures), 1)
                self.assertEqual(result.failures[0].retry_classification, 'inspect')
                self.assertEqual(docs[0]['items'][0]['external_id'], '123')

    def test_jimms_conflicting_product_metadata_retains_null_for_inspection(self):
        adapter = JimmsAdapter()
        sources = {adapter.page_url('gpu', 1): listing(adapter, None), product_url(adapter):
                   product_page() + '<meta itemprop="price" content="499.99">'}
        result, docs, _, _ = self.run_case(adapter, sources)
        self.assertEqual((result.status, result.exit_code, len(result.failures)), ('partial', 1, 1))
        self.assertEqual((result.failures[0].reason, result.failures[0].retry_classification), ('conflicting_price', 'inspect'))
        self.assertEqual(docs[0]['source_type'], 'product')
        self.assertIsNone(docs[0]['items'][0]['price_cents'])

    def test_source_http_and_connection_failures_match_for_both_retailers(self):
        for factory in ADAPTERS:
            for failure in (429, 500, 503, 404, 410, requests.Timeout('timeout'), requests.ConnectionError('offline')):
                with self.subTest(retailer=factory.__name__, failure=failure):
                    adapter = factory()
                    url = adapter.page_url('gpu', 1)
                    value = response('', url, failure) if isinstance(failure, int) else failure
                    result, docs, _, _ = self.run_case(adapter, {url: value})
                    expected = 'unavailable' if failure in (404, 410) else 'retryable'
                    self.assertEqual((result.status, result.exit_code), ('failed', 1))
                    self.assertEqual(result.failures[0].retry_classification, expected)
                    self.assertEqual(result.counters.network_responses, int(isinstance(failure, int)))
                    self.assertEqual(result.counters.source_failures, 1)
                    self.assertEqual(docs, [])

    def test_robots_unavailable_keeps_cause_without_counting_source_responses(self):
        for factory in ADAPTERS:
            for problem in (503, requests.Timeout('robots timeout')):
                with self.subTest(retailer=factory.__name__, problem=problem):
                    robots = response('', 'https://example/robots.txt', problem) if isinstance(problem, int) else problem
                    result, docs, calls, _ = self.run_case(factory(), {}, robots=robots)
                    self.assertEqual((result.status, result.exit_code), ('failed', 1))
                    self.assertEqual((result.failures[0].reason, result.failures[0].retry_classification),
                                     ('robots_unavailable', 'retryable'))
                    self.assertEqual(result.counters.source_responses, 0)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(docs, [])

    def test_duplicate_cards_have_uniform_counts_for_both_retailers(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                sources = {adapter.page_url('gpu', 1): listing(adapter, extra=card(adapter))}
                result, docs, _, _ = self.run_case(adapter, sources)
                self.assertEqual((result.status, result.items_found, result.counters.unique_products_identified), ('ok', 1, 1))
                self.assertEqual((result.counters.observations_saved, result.counters.duplicates_skipped), (1, 1))
                self.assertEqual(len(docs[0]['items']), 1)

    def test_write_failure_preserves_earlier_observations_for_both_retailers(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                sources = {adapter.page_url('gpu', page): listing(adapter, number=page + 122) for page in (1, 2)}
                def writer_factory(root):
                    delegate = RawDataWriter(root)
                    wrapper = Mock()
                    def write(**kwargs):
                        if kwargs['page'] == 2:
                            raise OSError('disk full')
                        return delegate.write(**kwargs)
                    wrapper.write.side_effect = write
                    return wrapper
                result, docs, _, _ = self.run_case(adapter, sources, pages=2, writer=writer_factory)
                self.assertEqual((result.status, result.exit_code, result.items_found), ('partial', 1, 1))
                self.assertEqual((result.failures[0].reason, result.failures[0].retry_classification), ('write_error', 'inspect'))
                self.assertEqual(result.counters.observations_saved, 1)
                self.assertEqual(docs[0]['items'][0]['external_id'], '123')

    def test_atomic_writer_failure_leaves_no_partial_json_or_temporary_file(self):
        from scraper.common import raw_data
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                def writer_factory(root):
                    delegate = RawDataWriter(root)
                    original_html = root / 'raw/html/original.html'
                    original_html.parent.mkdir(parents=True, exist_ok=True)
                    original_html.write_text('original source')
                    from scraper.common.raw_data import RawProduct
                    delegate.write(shop=adapter.config.name, category='gpu', source_type='category',
                        source_url=adapter.category_url('gpu'), raw_path=original_html, page=1,
                        items=[RawProduct('Previous GPU', 10000, product_url(adapter, 999))])
                    create = raw_data.NamedTemporaryFile
                    def broken_temporary(**kwargs):
                        temporary = create(**kwargs)
                        write = temporary.write
                        def fail(text):
                            write(text[:10])
                            temporary.flush()
                            raise OSError('simulated incomplete write')
                        temporary.write = fail
                        return temporary
                    wrapper = Mock()
                    def write(**kwargs):
                        with patch.object(raw_data, 'NamedTemporaryFile', side_effect=broken_temporary):
                            return delegate.write(**kwargs)
                    wrapper.write.side_effect = write
                    return wrapper
                result, docs, _, root = self.run_case(adapter, {adapter.page_url('gpu', 1): listing(adapter)}, writer=writer_factory)
                self.assertEqual((result.status, result.exit_code, result.items_found), ('failed', 1, 0))
                self.assertEqual(docs, [])
                self.assertEqual(len(list((root / 'raw').glob('*.json'))), 1)  # original survives
                self.assertEqual(list((root / 'raw').glob('*.tmp')), [])

    def test_cached_replays_use_distinct_run_ids_without_freshening_observation_time(self):
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                adapter = factory()
                url = adapter.page_url('gpu', 1)
                first, first_docs, _, _ = self.run_case(adapter, {url: listing(adapter)}, cached=(url,), offline=True)
                second, second_docs, _, _ = self.run_case(adapter, {url: listing(adapter)}, cached=(url,), offline=True)
                self.assertNotEqual(first.run_id, second.run_id)
                self.assertEqual(first_docs[0]['fetched_at'], second_docs[0]['fetched_at'])

    def test_manual_jimms_product_without_price_is_retained_as_null(self):
        adapter = JimmsAdapter()
        request = ProductRequest('gpu', product_url(adapter), external_id='123', retailer_sku='SKU-123')
        result, docs, _, _ = self.run_case(adapter, {request.url: product_page(None)},
                                          categories=(), product_requests=(request,))
        self.assertEqual((result.status, result.exit_code, result.items_found), ('partial', 1, 1))
        self.assertEqual(result.counters.category_pages_attempted, 0)
        self.assertEqual(result.counters.product_followups_attempted, 1)
        self.assertEqual(docs[0]['source_type'], 'product')
        self.assertIsNone(docs[0]['items'][0]['price_cents'])
        self.assertEqual(docs[0]['items'][0]['retailer_sku'], 'SKU-123')

    def test_jimms_offline_fallback_miss_preserves_category_null(self):
        adapter = JimmsAdapter()
        url = adapter.page_url('gpu', 1)
        result, docs, calls, _ = self.run_case(adapter, {url: listing(adapter, None)}, cached=(url,), offline=True)
        self.assertEqual((result.status, result.exit_code, len(result.failures)), ('partial', 1, 1))
        self.assertEqual((result.failures[0].reason, result.failures[0].retry_classification),
                         ('offline_cache_missing', 'retryable'))
        self.assertEqual((result.counters.cache_hits, result.counters.network_responses, result.counters.source_failures), (1, 0, 1))
        self.assertEqual(calls, [])
        self.assertIsNone(docs[0]['items'][0]['price_cents'])
        self.assertEqual(docs[0]['fetched_at'], '2023-11-14T22:13:20+00:00')

    def test_jimms_robots_blocked_fallback_never_requests_product(self):
        adapter = JimmsAdapter()
        category = adapter.page_url('gpu', 1)
        result, docs, calls, _ = self.run_case(adapter, {category: listing(adapter, None)},
            robots='User-agent: *\nDisallow: /fi/Product/Show/\n')
        self.assertEqual((result.status, result.exit_code, len(result.failures)), ('partial', 1, 1))
        self.assertEqual(result.failures[0].retry_classification, 'blocked')
        self.assertNotIn(product_url(adapter), calls)
        self.assertEqual(result.counters.network_responses, 1)
        self.assertIsNone(docs[0]['items'][0]['price_cents'])

    def test_manual_url_without_product_identity_does_not_create_invented_observation(self):
        adapter = JimmsAdapter()
        request = ProductRequest('gpu', product_url(adapter))
        result, docs, _, _ = self.run_case(adapter, {request.url: '<html>Unexpected response</html>'},
                                          categories=(), product_requests=(request,))
        self.assertEqual((result.status, result.exit_code, result.items_found), ('failed', 1, 0))
        self.assertEqual(result.failures[0].retry_classification, 'inspect')
        self.assertEqual(result.counters.unique_products_identified, 0)
        self.assertEqual(docs, [])

    def test_refresh_stops_before_publication_on_partial_collection_for_both(self):
        import argparse
        from scraper.cli import main
        from scraper.pipeline.refresh import RefreshPipeline
        for factory in ADAPTERS:
            with self.subTest(retailer=factory.__name__):
                root = Path(self.context.enter_context(tempfile.TemporaryDirectory()))
                adapter = factory()
                fetcher = PageFetcher(root / 'raw/html', adapter.config.key, set(adapter.config.allowed_hosts))
                sources = {adapter.page_url('gpu', 1): listing(adapter, None)}
                if adapter.config.capabilities.product_prices:
                    sources[product_url(adapter)] = product_page(None)
                for url, html in sources.items():
                    path = fetcher.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.html')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(html)
                fetcher.close()
                options = argparse.Namespace(skip_scrape=False, skip_specs=True, cold=False, pages=1, delay=1.0,
                    jimms_input=None, jimms_category_url=None, data_dir=root, web_output=root / 'web/components.json')
                stages = []
                def runner(name, args):
                    stages.append(name)
                    self.assertEqual(name, adapter.config.key + '-collect')
                    with patch('requests.Session.get', side_effect=AssertionError('offline request')):
                        code = main([*args, '--offline'])
                    return {'ok': code == 0, 'returncode': code, 'last_lines': ['partial collection']}
                self.assertEqual(RefreshPipeline(options, ['gpu'], [adapter.config.key],
                    project_root=root, log_path=root / 'refresh_log.jsonl', stage_runner=runner).run(), 1)
                self.assertEqual(stages, [adapter.config.key + '-collect'])
                self.assertFalse(options.web_output.exists())
                self.assertFalse((root / 'normalised/components.json').exists())
                record = json.loads((root / 'raw/scrape_runs.jsonl').read_text())
                self.assertEqual((record['status'], record['exit_code']), ('partial', 1))
                self.assertEqual(record['counters']['null_price_observations'], 1)

    def test_unsupported_operation_classifies_as_blocked(self):
        self.assertEqual(classify_problem(UnsupportedOperationError('unsupported')), ('unsupported_operation', 'blocked'))
        self.assertFalse(DatatronicAdapter().config.capabilities.product_prices)


if __name__ == '__main__':
    unittest.main()
