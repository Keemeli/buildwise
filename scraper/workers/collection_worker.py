"""Adapter-driven price collection, source persistence and one run result."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import json
import sys
from pathlib import Path
import requests

from scraper.common.fetching import PageFetcher
from scraper.common.raw_data import RawDataWriter
from scraper.retailers.contracts import ParseIssue, ProductRequest, RetailerAdapter


@dataclass(frozen=True)
class CollectionFailure:
    stage: str
    category: str
    url: str
    error: str


@dataclass(frozen=True)
class CollectionResult:
    shop: str
    categories: tuple[str, ...]
    pages_fetched: int
    products_fetched: int
    items_found: int
    duplicates_skipped: int
    started_at: str
    finished_at: str
    failures: tuple[CollectionFailure, ...]
    issues: tuple[ParseIssue, ...]

    @property
    def status(self) -> str:
        return ('partial' if self.items_found else 'failed') if self.failures else 'ok'

    @property
    def exit_code(self) -> int:
        return 1 if self.failures else 0

    def to_dict(self) -> dict:
        return {**asdict(self), 'status': self.status}


class CollectionWorker:
    """Own one fetcher across category pages and explicit product follow-ups.

    Adapter parsing is retailer-specific; this loop contains no retailer names.
    Source response metadata always comes from the fetcher, not from the parser.
    """

    def __init__(self, adapter: RetailerAdapter, data_dir: Path, fetcher: PageFetcher,
                 categories=(), pages: int = 1, product_requests=(), raw_writer=None,
                 category_url_overrides=None):
        if type(pages) is not int or pages < 1:
            raise ValueError('pages must be positive')
        self.adapter, self.data_dir, self.fetcher = adapter, data_dir, fetcher
        self.categories = tuple(dict.fromkeys(categories))
        self.pages = pages
        self.product_requests = tuple(product_requests)
        self.raw_writer = raw_writer if raw_writer is not None else RawDataWriter(data_dir)
        self.overrides = dict(category_url_overrides or {})

    def run(self) -> CollectionResult:
        self.started = datetime.now(timezone.utc).isoformat(timespec='seconds')
        self.pages_fetched = self.products_fetched = self.items_found = self.duplicates = 0
        self.failures, self.issues, self.queue = [], [], []
        self.visited_pages, self.queued_products, self.observed_products = set(), set(), set()
        self.written_products = set()
        try:
            # Preflight every input before issuing the first request.
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
                if request.url not in self.observed_products:
                    self._collect_product(request)
                else:
                    self.duplicates += 1
            result = CollectionResult(
                shop=self.adapter.config.name, categories=tuple(dict.fromkeys(
                    [*self.categories, *(r.category for r in self.product_requests)])),
                pages_fetched=self.pages_fetched, products_fetched=self.products_fetched,
                items_found=self.items_found, duplicates_skipped=self.duplicates,
                started_at=self.started, finished_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                failures=tuple(self.failures), issues=tuple(self.issues))
            raw_dir = self.data_dir / 'raw'
            raw_dir.mkdir(parents=True, exist_ok=True)
            with (raw_dir / 'scrape_runs.jsonl').open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(result.to_dict(), ensure_ascii=False) + '\n')
            print(f'{result.status}: {result.items_found} products, {len(result.failures)} failures')
            return result
        finally:
            self.fetcher.close()

    def _validate_request(self, request: ProductRequest) -> None:
        if not self.adapter.config.capabilities.product_prices:
            raise ValueError(f'{self.adapter.config.name} does not support product-page prices')
        self.adapter.config.validate_url(request.url)

    def _enqueue(self, request: ProductRequest) -> None:
        self._validate_request(request)
        if request.url in self.queued_products:
            self.duplicates += 1
        else:
            self.queued_products.add(request.url)
            self.queue.append(request)

    def _collect_category(self, category: str) -> None:
        signatures = set()
        for page in range(1, self.pages + 1):
            url = self.adapter.page_url(category, page, category_url=self.overrides[category]) \
                if category in self.overrides else self.adapter.page_url(category, page)
            if url in self.visited_pages:
                self.duplicates += 1
                continue
            self.visited_pages.add(url)
            try:
                html, path, origin = self.fetcher.fetch(url)
                self.pages_fetched += 1
                result = self.adapter.parse_category(html, category, url)
                self.issues.extend(result.issues)
                signature = frozenset([*(p.url for p in result.observations),
                                       *(r.url for r in result.product_requests)])
                if not signature:
                    raise ValueError('no identifiable products in category response')
                if signature in signatures:
                    raise ValueError('repeated listing page; pagination may be ignored or exhausted')
                signatures.add(signature)
                for request in result.product_requests:
                    self._enqueue(request)
                products = []
                seen = set(self.written_products)
                for product in result.observations:
                    if product.url in seen:
                        self.duplicates += 1
                    else:
                        seen.add(product.url)
                        products.append(product)
                if products:
                    self.raw_writer.write(shop=self.adapter.config.name, category=category,
                        source_type='category', source_url=url, raw_path=path, items=products,
                        page=page, site_total_products=result.site_total_products, origin=origin)
                    self.written_products.update(p.url for p in products)
                    self.observed_products.update(p.url for p in products if p.price_cents is not None)
                    self.items_found += len(products)
                print(f'  [{category}] page {page}: {len(products)} products ({origin})')
            except (requests.RequestException, OSError, ValueError) as exc:
                self.failures.append(CollectionFailure('category', category, url, str(exc)))
                print(f'  FAILED {url} — {exc}', file=sys.stderr)
                # Keep earlier pages and continue with the next requested category.
                break

    def _collect_product(self, request: ProductRequest) -> None:
        try:
            html, path, origin = self.fetcher.fetch(request.url)
            self.products_fetched += 1
            product = self.adapter.parse_product(html, request)
            for field in ('external_id', 'retailer_sku'):
                expected, actual = getattr(request, field), getattr(product, field)
                if expected is not None and actual is not None and expected != actual:
                    raise ValueError(f'product response conflicts with requested {field}')
            product = replace(product, external_id=product.external_id or request.external_id,
                              retailer_sku=product.retailer_sku or request.retailer_sku)
            if product.price_cents is None:
                raise ValueError('product response has no price')
            self.raw_writer.write(shop=self.adapter.config.name, category=request.category,
                source_type='product', source_url=request.url, raw_path=path, items=[product], origin=origin)
            if request.url not in self.written_products:
                self.items_found += 1
            self.written_products.add(request.url)
            self.observed_products.add(request.url)
        except (requests.RequestException, OSError, ValueError) as exc:
            self.failures.append(CollectionFailure('product', request.category, request.url, str(exc)))
            print(f'  FAILED {request.url} — {exc}', file=sys.stderr)
