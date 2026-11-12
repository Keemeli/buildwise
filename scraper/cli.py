"""BuildWise — one command surface for collection and catalogue publication.

    python3 -m scraper collect --shop jimms --category gpu --pages 2
    python3 -m scraper specs --shop datatronic --category gpu
    python3 -m scraper refresh --shops jimms,datatronic --categories gpu
    python3 -m scraper refresh --offline

Commands validate arguments before creating workers. Retailer-specific HTML,
network policy and catalogue transformations stay in their implementation modules.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from scraper.config import PROJECT_ROOT, CATEGORIES, RAW_DIR, NORMALISED_DIR
from scraper.pipeline.export import CatalogueExporter
from scraper.pipeline.normalisation import ComponentNormaliser
from scraper.pipeline.refresh import RefreshPipeline
from scraper.retailers.registry import default_registry


class ScraperCLI:
    """Build command arguments and dispatch to independently testable workers."""

    def __init__(self, registry=None):
        self.registry = default_registry() if registry is None else registry
        self.parser = argparse.ArgumentParser(prog="python3 -m scraper", description="BuildWise retailer data pipeline")
        commands = self.parser.add_subparsers(dest="command", required=True)
        collect = commands.add_parser("collect", help="collect retailer names and prices")
        collect.add_argument("--shop", required=True, choices=self.registry.keys)
        collect.add_argument("--category", action="append", choices=CATEGORIES)
        collect.add_argument("--all", action="store_true", help="all configured categories")
        collect.add_argument("--url", help="override retailer category URL (one category)")
        collect.add_argument("--input", type=Path, help="existing product manifest (requires product-price support)")
        collect.add_argument("--pages", type=int, default=1)
        self._network_options(collect)
        collect.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")

        retry = commands.add_parser("retry", help="retry eligible pending collection work")
        retry.add_argument("--shop", required=True, choices=self.registry.keys)
        retry.add_argument("--limit", type=int, default=25, help="maximum pending entries to attempt")
        retry.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
        self._network_options(retry)

        specs = commands.add_parser("specs", help="collect product-page specifications")
        specs.add_argument("--shop", required=True, choices=("datatronic",))
        specs.add_argument("--category", action="append", choices=CATEGORIES)
        specs.add_argument("--raw-dir", type=Path, default=RAW_DIR)
        specs.add_argument("--out", type=Path, default=NORMALISED_DIR)
        specs.add_argument("--limit", type=int)
        specs.add_argument("--delay", type=float, default=1.0)
        mode = specs.add_mutually_exclusive_group()
        mode.add_argument("--force", action="store_true")
        mode.add_argument("--offline", "--reparse", dest="reparse", action="store_true",
                          help="reparse today's cached product pages without network")
        specs.add_argument("--status", action="store_true")
        specs.add_argument("--checkpoint-every", type=int, default=25)

        normalise = commands.add_parser("normalise", help="build catalogue from saved observations")
        normalise.add_argument("--raw-dir", type=Path, default=RAW_DIR)
        normalise.add_argument("--out", type=Path, default=NORMALISED_DIR)
        normalise.add_argument("--category", choices=CATEGORIES)
        export = commands.add_parser("export", help="publish catalogue or check web-copy drift")
        export.add_argument("--check", action="store_true")
        export.add_argument("--source", type=Path, default=NORMALISED_DIR / "components.json")
        export.add_argument("--target", type=Path, default=PROJECT_ROOT / "web/data/components.json")

        refresh = commands.add_parser("refresh", help="collect, enrich, normalise and export")
        refresh.add_argument("--shops", default="datatronic")
        refresh.add_argument("--categories", help="comma-separated categories")
        refresh.add_argument("--pages", type=int, default=2)
        refresh.add_argument("--delay", type=float, default=1.0)
        refresh.add_argument("--skip-scrape", action="store_true")
        refresh.add_argument("--skip-specs", action="store_true")
        refresh.add_argument("--offline", action="store_true", help="normalise and export only")
        refresh.add_argument("--cold", action="store_true", help="force Datatronic specification refresh")
        refresh.add_argument("--input", type=Path, help="product manifest for a single retailer")
        refresh.add_argument("--url", help="category URL override for a single retailer/category")
        refresh.add_argument("--jimms-input", type=Path, help="legacy Jimms manifest option")
        refresh.add_argument("--jimms-category-url")
        refresh.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
        refresh.add_argument("--web-output", type=Path, default=PROJECT_ROOT / "web/data/components.json")

    @staticmethod
    def _network_options(parser):
        parser.add_argument("--delay", type=float, default=1.0)
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--offline", action="store_true", help="only read today's HTML cache")
        mode.add_argument("--force", action="store_true", help="refetch today's cached HTML")

    def run(self, argv=None) -> int:
        args = self.parser.parse_args(argv)
        if hasattr(args, "delay") and (not math.isfinite(args.delay) or args.delay < 1):
            self.parser.error("delay must be finite and at least 1 second")
        if hasattr(args, "pages") and args.pages < 1:
            self.parser.error("pages must be positive")
        try:
            if args.command == "collect":
                if args.all and args.category:
                    raise ValueError("use --all or --category, not both")
                if args.input and (args.category or args.all or args.url):
                    raise ValueError("--input cannot be combined with categories or --url")
                if args.url and (len(args.category or []) != 1 or args.all):
                    raise ValueError("--url needs exactly one --category")
                adapter = self.registry.get(args.shop)
                if args.all:
                    args.category = list(adapter.config.category_paths)
                if not args.input and not args.category:
                    raise ValueError("supply --category, --all or an --input manifest")
                from scraper.workers.collection import CollectionService
                return CollectionService(args, adapter=adapter, registry=self.registry).run()
            if args.command == "retry":
                if args.limit < 1:
                    raise ValueError("limit must be positive")
                from scraper.workers.retry import RetryService
                return RetryService(args, self.registry.get(args.shop)).run()
            if args.command == "specs":
                if args.checkpoint_every < 1 or (args.limit is not None and args.limit < 1):
                    raise ValueError("checkpoint-every and limit must be positive")
                from scraper.workers.specifications import DatatronicSpecExtractor
                return DatatronicSpecExtractor(args).run()
            if args.command == "normalise":
                return ComponentNormaliser(args.raw_dir, args.out, args.category).run()
            if args.command == "export":
                return CatalogueExporter(args.source, args.target).run(check=args.check)
            shops = list(dict.fromkeys(shop.strip().lower() for shop in args.shops.split(',')))
            if any(shop not in self.registry.keys for shop in shops):
                raise ValueError("unknown retailer in --shops")
            categories = args.categories.split(',') if args.categories else list(CATEGORIES)
            categories = list(dict.fromkeys(c.strip() for c in categories))
            if any(category not in CATEGORIES for category in categories):
                raise ValueError("unknown component category")
            if args.offline:
                args.skip_scrape = args.skip_specs = True
            return RefreshPipeline(args, categories, shops, registry=self.registry).run()
        except (OSError, ValueError) as exc:
            self.parser.error(str(exc))


def main(argv=None) -> int:
    return ScraperCLI().run(argv)
