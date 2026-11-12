"""Jimms category discovery and product-price collection workers.

Discovery and price reads share a fetcher interface but retain their separate
output contracts. These workers contain no command-line argument parsing.
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import requests
from scraper.common.fetching import PageFetcher
from scraper.common.raw_data import RawProduct, RawDataWriter
from scraper.retailers.jimms import HOSTS, SHOP, JimmsParser, parse_product, parse_category
from scraper.config import PROJECT_ROOT, CATEGORIES


def page_url(url: str, page: int) -> str:
    """Replace the page parameter while retaining other category filters."""
    parsed = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() != 'page']
    query.append(('page', str(page)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))


class JimmsCategoryDiscovery:
    """Discover a bounded category into a manifest without replacing good output
    after an incomplete run. Fetching and HTML parsing are separate collaborators.
    """

    def __init__(self, options: argparse.Namespace, fetcher: PageFetcher,
                 category_parser: JimmsParser | None = None):
        self.options = options
        self.fetcher = fetcher
        self.category_parser = category_parser or JimmsParser()

    def run(self, close_fetcher: bool = True) -> int:
        items, sources, seen_pages = {}, [], set()
        failed = None
        try:
            for page in range(1, self.options.pages + 1):
                url = page_url(self.options.url, page)
                try:
                    html, path, origin = self.fetcher.fetch(url)
                    urls = self.category_parser.parse_category(html, url)
                    signature = frozenset(urls)
                    if signature in seen_pages:
                        raise ValueError('repeated listing page; pagination may be ignored or exhausted')
                    seen_pages.add(signature)
                    for product_url in urls:
                        items.setdefault(product_url, {'category': self.options.category, 'url': product_url})
                    sources.append({'page': page, 'url': url, 'raw_html': str(path),
                                    'origin': origin, 'products_found': len(urls)})
                    print(f'  page {page}: {len(urls)} products ({origin})')
                except (requests.RequestException, OSError, ValueError) as exc:
                    failed = {'page': page, 'url': url, 'error': str(exc)}
                    print(f'  FAILED page {page}: {exc}', file=sys.stderr)
                    break
        finally:
            if close_fetcher:
                self.fetcher.close()
        # Do not replace a usable manifest with incomplete discovery results.
        report = {'category': self.options.category, 'pages_requested': self.options.pages,
                  'pages': sources, 'unique_products': len(items), 'failure': failed,
                  'status': 'failed' if failed else 'ok'}
        self.options.output.parent.mkdir(parents=True, exist_ok=True)
        self.options.output.with_suffix('.report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        if failed:
            return 1
        self.options.output.write_text(json.dumps(list(items.values()), ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'wrote {len(items)} product URLs to {self.options.output}')
        return 0


class JimmsPriceScraper:
    """Collect a validated manifest, retaining each observation's source and time.

    Inject a fetcher or parser to reuse the worker without making real requests.
    The worker closes its fetcher when a run finishes, including failed runs.
    """

    def __init__(self, manifest: list[dict], data_dir: Path, fetcher: PageFetcher,
                 product_parser: JimmsParser | None = None, raw_writer: RawDataWriter | None = None):
        self.manifest = manifest
        self.data_dir = data_dir
        self.raw_dir = data_dir / "raw"
        self.fetcher = fetcher
        self.product_parser = product_parser or JimmsParser()
        self.raw_writer = raw_writer if raw_writer is not None else RawDataWriter(data_dir)

    def run(self, close_fetcher: bool = True) -> int:
        started = datetime.now(timezone.utc)
        groups: dict[str, list] = {}
        failures = []
        try:
            for entry in self.manifest:
                url, category = entry["url"], entry["category"]
                try:
                    html, path, origin = self.fetcher.fetch(url)
                    product = self.product_parser.parse_product(html)
                    item = RawProduct.from_item({**product, "url": url, "external_id": None})
                    groups.setdefault(category, []).append((item, path, origin))
                    print(f"  [{category}] {product['name']} — {product['price_cents'] / 100:.2f} EUR ({origin})")
                except (requests.RequestException, OSError, ValueError) as exc:
                    failures.append({"url": url, "category": category, "error": str(exc)})
                    print(f"  FAILED {url} — {exc}", file=sys.stderr)
        finally:
            if close_fetcher:
                self.fetcher.close()

        self.raw_dir.mkdir(parents=True, exist_ok=True)
        # One product response per document; page is null, never a SKU counter.
        for category, products in groups.items():
            for item, path, origin in products:
                self.raw_writer.write(shop=SHOP, category=category, source_type="product",
                                      source_url=item.url, raw_path=path, origin=origin, items=[item])
        record = {"shop": SHOP, "started_at": started.isoformat(timespec="seconds"),
                  "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "items_found": sum(map(len, groups.values())), "failures": failures,
                  "status": "partial" if failures and groups else "failed" if failures else "ok"}
        with (self.raw_dir / "scrape_runs.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(f"{record['status']}: {record['items_found']} products, {len(failures)} failures")
        return 1 if failures else 0
