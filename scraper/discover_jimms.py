#!/usr/bin/env python3
"""BuildWise data worker — Jimms category product URL discovery.

Fetches a bounded number of category pages and writes the explicit URL manifest
consumed by scrape_jimms.py. Prices still come from product-page metadata.

Usage:
    python scraper/discover_jimms.py --category gpu --url <category-url> --pages 1
    python scraper/scrape_jimms.py --input jimms_discovered.json

Etiquette:
    * same robots checks, request spacing and daily cache as product scraping
    * explicit page limit; no API calls, browser automation or recursive crawling
    * repeated pages are reported, never counted as additional catalogue coverage
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from common.fetching import PageFetcher
from retailers.jimms import HOSTS, parse_category
from scrape_jimms import CATEGORIES, PROJECT_ROOT


def page_url(url: str, page: int) -> str:
    """Replace the page parameter while retaining other category filters."""
    parsed = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() != 'page']
    query.append(('page', str(page)))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ''))


def main() -> int:
    parser = argparse.ArgumentParser(description='Discover Jimms category product URLs.')
    parser.add_argument('--category', required=True, choices=sorted(CATEGORIES))
    parser.add_argument('--url', required=True, help='Jimms /fi/Product/List/ URL')
    parser.add_argument('--pages', type=int, default=1, help='maximum listing pages (default 1)')
    parser.add_argument('--output', type=Path, default=Path('jimms_discovered.json'))
    parser.add_argument('--data-dir', type=Path, default=PROJECT_ROOT / 'data')
    parser.add_argument('--delay', type=float, default=1.0)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--offline', action='store_true')
    mode.add_argument('--force', action='store_true')
    args = parser.parse_args()
    if args.pages < 1 or not math.isfinite(args.delay) or args.delay < 1:
        parser.error('pages must be positive and delay must be finite and >= 1')
    fetcher = PageFetcher(args.data_dir / 'raw' / 'html', 'jimms', HOSTS,
                          args.delay, args.offline, args.force)
    try:
        fetcher.validate_url(args.url)
        if not urlsplit(args.url).path.startswith('/fi/Product/List/'):
            raise ValueError('expected a Jimms /fi/Product/List/ category URL')
    except ValueError as exc:
        fetcher.close()
        parser.error(str(exc))
    items, sources, seen_pages = {}, [], set()
    failed = None
    try:
        for page in range(1, args.pages + 1):
            url = page_url(args.url, page)
            try:
                html, path, origin = fetcher.fetch(url)
                urls = parse_category(html, url)
                signature = frozenset(urls)
                if signature in seen_pages:
                    raise ValueError('repeated listing page; pagination may be ignored or exhausted')
                seen_pages.add(signature)
                for product_url in urls:
                    items.setdefault(product_url, {'category': args.category, 'url': product_url})
                sources.append({'page': page, 'url': url, 'raw_html': str(path),
                                'origin': origin, 'products_found': len(urls)})
                print(f'  page {page}: {len(urls)} products ({origin})')
            except (requests.RequestException, OSError, ValueError) as exc:
                failed = {'page': page, 'url': url, 'error': str(exc)}
                print(f'  FAILED page {page}: {exc}', file=sys.stderr)
                break
    finally:
        fetcher.close()
    # Do not replace a usable manifest with incomplete discovery results.
    report = {'category': args.category, 'pages_requested': args.pages,
              'pages': sources, 'unique_products': len(items), 'failure': failed,
              'status': 'failed' if failed else 'ok'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix('.report.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if failed:
        return 1
    args.output.write_text(json.dumps(list(items.values()), ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote {len(items)} product URLs to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
