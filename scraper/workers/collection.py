"""One collection service; each retailer keeps its own parsing strategy."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from scraper.common.fetching import PageFetcher
from scraper.config import CATEGORIES
from scraper.retailers.jimms import HOSTS, CATEGORY_URLS
from scraper.workers.datatronic import DatatronicScraper
from scraper.workers.jimms import JimmsCategoryDiscovery, JimmsPriceScraper


class CollectionService:
    """Collect category prices through a single retailer-independent interface.

    Jimms discovery is an internal phase. One fetcher spans both phases, so
    request spacing and robots state survive the transition to product pages.
    """

    def __init__(self, options: argparse.Namespace):
        self.options = options

    @staticmethod
    def read_manifest(path: Path) -> list[dict]:
        """Validate the existing category/url manifest before any requests."""
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, list) or not manifest:
            raise ValueError("input must be a non-empty JSON list")
        seen = set()
        for entry in manifest:
            if not isinstance(entry, dict) or entry.get("category") not in CATEGORIES:
                raise ValueError("each entry needs a supported category")
            url = entry.get("url")
            if not isinstance(url, str) or not url.strip():
                raise ValueError("each entry needs a product URL")
            if url in seen:
                raise ValueError(f"duplicate URL: {url}")
            seen.add(url)
        return manifest

    def run(self) -> int:
        args = self.options
        if args.shop == "datatronic":
            fetcher = PageFetcher(args.data_dir / "raw/html", "datatronic",
                                  {"datatronic.fi", "www.datatronic.fi"},
                                  args.delay, args.offline, args.force)
            return DatatronicScraper(args.category, args.pages, args.delay,
                                     fetcher=fetcher, data_dir=args.data_dir).run()

        manifest = self.read_manifest(args.input) if args.input else []
        fetcher = PageFetcher(args.data_dir / "raw/html", "jimms", HOSTS,
                              args.delay, args.offline, args.force)
        try:
            # Preflight every requested category or product before output/network.
            urls = []
            if args.input:
                for entry in manifest:
                    fetcher.validate_url(entry["url"])
            else:
                for category in args.category:
                    url = args.url or CATEGORY_URLS.get(category)
                    if not url:
                        raise ValueError(f"no configured Jimms URL for {category}; supply --url with one category")
                    fetcher.validate_url(url)
                    if not urlsplit(url).path.startswith('/fi/Product/List/'):
                        raise ValueError("expected a Jimms /fi/Product/List/ category URL")
                    urls.append((category, url))
                for category, url in urls:
                    output = args.data_dir / "discovery" / f"jimms_{category}.json"
                    options = argparse.Namespace(category=category, url=url, pages=args.pages, output=output)
                    if JimmsCategoryDiscovery(options, fetcher).run(close_fetcher=False):
                        return 1
                    manifest.extend(self.read_manifest(output))
            # Overlapping categories may discover the same URL; keep the first.
            unique = {}
            for entry in manifest:
                unique.setdefault(entry['url'], entry)
            manifest = list(unique.values())
            return JimmsPriceScraper(manifest, args.data_dir, fetcher).run(close_fetcher=False)
        finally:
            fetcher.close()
