"""Adapter-driven collection with explicit unresolved outcomes and run identity."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from uuid import uuid4
import requests

from scraper.common.raw_data import RawDataWriter
from scraper.workers.pending_work import PendingWorkStore
from scraper.retailers.contracts import (
    PriceExtractionError, ProductRequest, RetailerAdapter, UnsupportedOperationError,
)
from scraper.workers.collection_reporting import (
    CollectionCounters, CollectionOutcome, CollectionResult, classify_problem,
)


@dataclass(frozen=True)
class SourceContext:
    category: str
    source_type: str
    source_url: str
    raw_path: Path
    origin: str
    page: int | None = None
    site_total_products: int | None = None


class CollectionWorker:
    """Own a run and preserve identified products when their prices are unknown.

    Deferred null observations are in-memory source context for this run only.
    The run report describes unresolved work; it does not schedule retries.
    """

    def __init__(self, adapter: RetailerAdapter, data_dir: Path, fetcher,
                 categories=(), pages: int = 1, product_requests=(), raw_writer=None,
                 category_url_overrides=None, start_page=1, close_fetcher=True):
        if type(pages) is not int or pages < 1:
            raise ValueError('pages must be positive')
        if type(start_page) is not int or start_page < 1:
            raise ValueError('start_page must be positive')
        self.start_page = start_page
        self.close_fetcher = close_fetcher
        self.adapter, self.data_dir, self.fetcher = adapter, data_dir, fetcher
        self.categories = tuple(dict.fromkeys(categories))
        self.pages, self.product_requests = pages, tuple(product_requests)
        self.raw_writer = raw_writer if raw_writer is not None else RawDataWriter(data_dir)
        self.overrides = dict(category_url_overrides or {})

    def run(self) -> CollectionResult:
        self.run_id = uuid4().hex
        started = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.counters = CollectionCounters(category_pages_planned=len(self.categories) * self.pages)
        self.pages_fetched = self.products_fetched = 0
        self.issues, self.queue, self.coverage = [], [], []
        self.outcomes, self.recovered, self.deferred = {}, {}, {}
        self.identified, self.saved, self.priced = set(), set(), set()
        self.visited_pages, self.queued_products, self.failed_sources = set(), set(), set()
        try:
            # Invalid command inputs fail before the first request.
            for category in self.categories:
                self.adapter.category_url(category)
                if category in self.overrides:
                    self.adapter.config.validate_url(self.overrides[category])
            for request in self.product_requests:
                self._validate_request(request)
                self._enqueue(request)
            for category in self.categories:
                self._collect_category(category)
            for request in self.queue:
                if request.url in self.priced:
                    self.counters.duplicates_skipped += 1
                else:
                    self._collect_product(request)
            self._save_remaining_nulls()
            self.counters.unique_products_identified = len(self.identified)
            self.counters.source_failures = len(self.failed_sources)
            self.counters.recovered_issues = len(self.recovered)
            self.counters.unresolved_outcomes = len(self.outcomes)
            result = CollectionResult(
                run_id=self.run_id, shop=self.adapter.config.name,
                categories=tuple(dict.fromkeys([*self.categories, *(r.category for r in self.product_requests)])),
                pages_fetched=self.pages_fetched, products_fetched=self.products_fetched,
                items_found=len(self.saved), duplicates_skipped=self.counters.duplicates_skipped,
                started_at=started, finished_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                failures=tuple(self.outcomes.values()), issues=tuple(self.issues),
                recovered=tuple(self.recovered.values()), counters=self.counters, coverage=tuple(self.coverage))
            raw_dir = self.data_dir / 'raw'
            raw_dir.mkdir(parents=True, exist_ok=True)
            with (raw_dir / 'scrape_runs.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')
            contexts = {}
            for url, (_, context) in self.deferred.items():
                contexts[url] = {
                    'category': context.category, 'source_type': context.source_type,
                    'source_url': context.source_url,
                    'raw_html': context.raw_path.relative_to(self.data_dir).as_posix(),
                    'origin': context.origin, 'page': context.page,
                    'site_total_products': context.site_total_products,
                }
            PendingWorkStore(self.data_dir).record(result, self.outcomes, contexts)
            print(f'{result.status} [run {result.run_id}]: {result.items_found} products; '
                  f'{self.counters.observations_saved} observations '
                  f'({self.counters.priced_observations} priced, {self.counters.null_price_observations} null); '
                  f'{len(result.failures)} unresolved, {len(result.recovered)} recovered')
            print(f'  sources: {self.counters.cache_hits} cached, {self.counters.network_responses} network '
                  f'responses, {self.counters.source_failures} failed attempts')
            return result
        finally:
            if self.close_fetcher:
                self.fetcher.close()

    def _key(self, category, url, kind='product'):
        # Product work is unique by retailer URL, even if categories overlap.
        return kind, category if kind == 'category' else None, url

    def _record(self, category, url, source_url, stage, *, reason='missing_price', error=None,
                phase='parse', product=None, request=None, message=None, kind='product'):
        code, retry = classify_problem(error, reason=reason, stage=phase)
        identity = product if product is not None else request
        self.outcomes[self._key(category, url, kind)] = CollectionOutcome(
            self.run_id, self.adapter.config.name, stage, category, url, source_url, code, retry,
            message or (str(error) if error is not None else reason.replace('_', ' ')),
            getattr(identity, 'external_id', None), getattr(identity, 'retailer_sku', None))

    def _resolve(self, url):
        for key in list(self.outcomes):
            if key[0] == 'product' and key[2] == url:
                self.recovered[key] = self.outcomes.pop(key)
        self.deferred.pop(url, None)

    def _fetch(self, url):
        try:
            html, path, origin = self.fetcher.fetch(url)
        except requests.HTTPError as exc:
            if exc.response is not None:
                self.counters.network_responses += 1
                self.counters.source_responses += 1
            raise
        self.counters.source_responses += 1
        if origin == 'cache':
            self.counters.cache_hits += 1
        elif origin == 'network':
            self.counters.network_responses += 1
        return html, path, origin

    def _validate_request(self, request):
        if not self.adapter.config.capabilities.product_prices:
            raise UnsupportedOperationError(f'{self.adapter.config.name} does not support product-page prices')
        self.adapter.config.validate_url(request.url)

    def _enqueue(self, request):
        self._validate_request(request)
        if request.url in self.queued_products:
            self.counters.duplicates_skipped += 1
        else:
            self.queued_products.add(request.url)
            self.queue.append(request)

    def _save(self, context, products):
        self.raw_writer.write(shop=self.adapter.config.name, category=context.category,
            source_type=context.source_type, source_url=context.source_url, raw_path=context.raw_path,
            items=products, page=context.page, site_total_products=context.site_total_products,
            origin=context.origin, run_id=self.run_id)
        self.counters.observations_saved += len(products)
        self.counters.priced_observations += sum(p.price_cents is not None for p in products)
        self.counters.null_price_observations += sum(p.price_cents is None for p in products)
        self.saved.update(p.url for p in products)
        for product in products:
            if product.price_cents is not None:
                self.priced.add(product.url)
                self._resolve(product.url)

    def _defer(self, product, context, reason='missing_price'):
        self.identified.add(product.url)
        if product.url in self.priced:
            self.counters.duplicates_skipped += 1
            return
        if product.url in self.deferred and context.source_type == 'category':
            self.counters.duplicates_skipped += 1
        self.deferred[product.url] = product, context
        self._record(context.category, product.url, context.source_url, context.source_type,
                     reason=reason, product=product)

    def _category_issues(self, result, context):
        self.issues.extend(result.issues)
        requests = {r.url: r for r in result.product_requests}
        products = {p.url: p for p in result.observations}
        for issue in result.issues:
            if issue.code == 'duplicate_url':
                self.counters.duplicates_skipped += 1
                continue
            if issue.url in products or issue.url in requests:
                if issue.url in self.priced:
                    continue
                self._record(context.category, issue.url, context.source_url, 'category', reason=issue.code,
                             product=products.get(issue.url), request=requests.get(issue.url), message=issue.message)
            else:
                self._record(context.category, context.source_url, context.source_url, 'category',
                             reason=issue.code, message=issue.message, kind='category')
                self.failed_sources.add(('category', context.source_url))

    def _collect_category(self, category):
        signatures = set()
        for page in range(self.start_page, self.start_page + self.pages):
            url = self.adapter.page_url(category, page, category_url=self.overrides[category]) \
                if category in self.overrides else self.adapter.page_url(category, page)
            if url in self.visited_pages:
                self.counters.duplicates_skipped += 1
                continue
            self.visited_pages.add(url)
            self.counters.category_pages_attempted += 1
            phase = 'fetch'
            try:
                html, path, origin = self._fetch(url)
                self.pages_fetched += 1
                phase = 'parse'
                result = self.adapter.parse_category(html, category, url)
                context = SourceContext(category, 'category', url, path, origin, page, result.site_total_products)
                signature = frozenset([*(p.url for p in result.observations), *(r.url for r in result.product_requests)])
                if (not signature and not result.end_of_category) or signature and signature in signatures:
                    reason = 'empty_page' if not signature else 'repeated_page'
                    self._record(category, url, url, 'category', reason=reason, kind='category',
                                 message='repeated listing page; pagination may be ignored or exhausted'
                                 if reason == 'repeated_page' else 'empty listing without confirmed category end')
                    self.failed_sources.add(('category', url))
                    self.issues.extend(result.issues)
                    self.coverage.append({'category': category, 'reason': 'unresolved', 'last_page': page})
                    break
                if signature:
                    signatures.add(signature)
                self.counters.category_pages_processed += 1
                self.identified.update(signature)
                priced = []
                seen = set(self.priced)
                for product in result.observations:
                    if product.price_cents is None:
                        self._defer(product, context)
                    elif product.url in seen:
                        self.counters.duplicates_skipped += 1
                    else:
                        priced.append(product)
                        seen.add(product.url)
                self._category_issues(result, context)
                phase = 'write'
                if priced:
                    self._save(context, priced)
                for request in result.product_requests:
                    try:
                        self._enqueue(request)
                    except (ValueError, UnsupportedOperationError) as exc:
                        known = self.deferred.get(request.url)
                        self._record(category, request.url, url, 'product', error=exc,
                                     product=known[0] if known else None, request=request)
                print(f'  [{category}] page {page}: {len(result.observations)} identified observations ({origin})')
                if result.end_of_category:
                    self.coverage.append({'category': category, 'reason': 'confirmed_end',
                                          'evidence': result.end_reason, 'last_page': page})
                    break
            except (requests.RequestException, OSError, ValueError) as exc:
                self._record(category, url, url, 'category', error=exc, phase=phase, kind='category')
                self.failed_sources.add(('category', url))
                self.coverage.append({'category': category, 'reason': 'unresolved', 'last_page': page})
                print(f'  FAILED {url} — {exc}', file=sys.stderr)
                break
        else:
            self.coverage.append({'category': category, 'reason': 'page_limit', 'last_page': self.start_page + self.pages - 1})

    @staticmethod
    def _enrich(product, request):
        if product.url != request.url:
            raise ValueError('product response URL conflicts with its request')
        for field in ('external_id', 'retailer_sku'):
            expected, actual = getattr(request, field), getattr(product, field)
            if expected is not None and actual is not None and expected != actual:
                raise ValueError(f'product response conflicts with requested {field}')
        return replace(product, external_id=product.external_id or request.external_id,
                       retailer_sku=product.retailer_sku or request.retailer_sku)

    def _collect_product(self, request):
        self.counters.product_followups_attempted += 1
        phase = 'fetch'
        try:
            html, path, origin = self._fetch(request.url)
            self.products_fetched += 1
            context = SourceContext(request.category, 'product', request.url, path, origin)
            phase = 'parse'
            try:
                product = self.adapter.parse_product(html, request)
                reason = 'missing_price'
            except PriceExtractionError as exc:
                product, reason = exc.product, exc.reason
            product = self._enrich(product, request)
            self.identified.add(product.url)
            if product.price_cents is None:
                self._defer(product, context, reason)
                return
            phase = 'write'
            self._save(context, [product])
        except (requests.RequestException, OSError, ValueError) as exc:
            known = self.deferred.get(request.url)
            self._record(request.category, request.url, request.url, 'product', error=exc, phase=phase,
                         product=known[0] if known else None, request=request)
            self.failed_sources.add(('product', request.url))
            print(f'  FAILED {request.url} — {exc}', file=sys.stderr)

    def _save_remaining_nulls(self):
        groups = {}
        for product, context in self.deferred.values():
            groups.setdefault(context, []).append(product)
        for context, products in groups.items():
            try:
                self._save(context, products)
            except (OSError, ValueError) as exc:
                self.failed_sources.add((context.source_type, context.source_url))
                for product in products:
                    self._record(context.category, product.url, context.source_url, context.source_type,
                                 error=exc, phase='write', product=product)
