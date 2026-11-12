"""Validate a collection command and construct the shared adapter-driven worker."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from urllib.parse import urlsplit

from scraper.common.fetching import PageFetcher
from scraper.config import CATEGORIES
from scraper.retailers.contracts import ProductRequest, RetailerAdapter
from scraper.retailers.registry import default_registry
from scraper.workers.collection_worker import CollectionWorker


class CollectionService:
    def __init__(self, options, adapter: RetailerAdapter | None = None, registry=None):
        self.options = options
        self.registry = default_registry() if registry is None else registry
        self.adapter = adapter

    @staticmethod
    def read_manifest(path: Path) -> list[dict]:
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(manifest, list) or not manifest:
            raise ValueError('input must be a non-empty JSON list')
        seen = set()
        for entry in manifest:
            if not isinstance(entry, dict) or entry.get('category') not in CATEGORIES:
                raise ValueError('each entry needs a supported category')
            url = entry.get('url')
            if not isinstance(url, str) or not url.strip():
                raise ValueError('each entry needs a product URL')
            if url in seen:
                raise ValueError(f'duplicate URL: {url}')
            seen.add(url)
        return manifest

    def run(self) -> int:
        args = self.options
        adapter = self.registry.get(args.shop) if self.adapter is None else self.adapter
        categories = tuple(dict.fromkeys(args.category or ()))
        requests, overrides = [], {}
        if args.input:
            if not adapter.config.capabilities.product_prices:
                raise ValueError(f'{adapter.config.name} does not support product-page prices')
            for entry in self.read_manifest(args.input):
                adapter.config.validate_url(entry['url'])
                external_id = entry.get('external_id')
                requests.append(ProductRequest(entry['category'], entry['url'],
                    str(external_id) if external_id is not None else None,
                    reason='manifest', retailer_sku=entry.get('retailer_sku')))
        if args.url:
            if len(categories) != 1:
                raise ValueError('--url needs exactly one category')
            adapter.config.validate_url(args.url)
            parsed = urlsplit(args.url)
            paths = dict(adapter.config.category_paths)
            paths[categories[0]] = parsed.path + ('?' + parsed.query if parsed.query else '')
            adapter.config = replace(adapter.config, category_paths=paths)
            overrides[categories[0]] = args.url
        for category in categories:
            adapter.category_url(category)
        fetcher = PageFetcher(args.data_dir / 'raw/html', adapter.config.key,
            set(adapter.config.allowed_hosts), args.delay, args.offline, args.force)
        try:
            worker = CollectionWorker(adapter, args.data_dir, fetcher, categories, args.pages,
                                      product_requests=requests, category_url_overrides=overrides)
        except BaseException:
            fetcher.close()
            raise
        return worker.run().exit_code
