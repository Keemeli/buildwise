"""Datatronic listing collection and raw observation persistence."""
from __future__ import annotations
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
import requests
from scraper.common.fetching import PageFetcher
from scraper.common.raw_data import RawProduct, RawDataWriter
from scraper.retailers.datatronic import BASE_URL, SHOP, CATEGORIES, DatatronicParser, parse_listing
from scraper.config import PROJECT_ROOT, RAW_DIR as RAW_JSON_DIR, HTML_DIR as RAW_HTML_DIR

RUN_LOG = RAW_JSON_DIR / "scrape_runs.jsonl"


class DatatronicScraper:
    """Own one listing run, its parser, fetcher and output paths."""

    def __init__(self, categories: list[str], pages: int = 1, delay: float = 1.0,
                 project_root: Path | None = None, fetcher: PageFetcher | None = None,
                 listing_parser: DatatronicParser | None = None, data_dir: Path | None = None,
                 raw_writer: RawDataWriter | None = None):
        self.project_root = PROJECT_ROOT if project_root is None else project_root
        self.raw_dir = (self.project_root / "data" if data_dir is None else data_dir) / "raw"
        self.run_log = self.raw_dir / "scrape_runs.jsonl"
        self.raw_writer = raw_writer if raw_writer is not None else RawDataWriter(self.raw_dir.parent)
        self.categories, self.pages, self.delay = categories, pages, delay
        self.fetcher = fetcher if fetcher is not None else PageFetcher(
            self.raw_dir / "html", "datatronic", {"datatronic.fi", "www.datatronic.fi"}, delay)
        self.listing_parser = listing_parser or DatatronicParser()

    def save_items(self, category: str, page: int, items: list[dict], total: int | None,
                   url: str, raw_path: Path, run_date: str, origin: str | None = None) -> Path:
        """Use the shared raw contract; retain run_date for existing callers.

        The writer timestamps filenames independently so reruns preserve earlier
        observations. The HTML cache determines the observation's fetched_at.
        """
        return self.raw_writer.write(
            shop=SHOP["name"], category=category, source_type="category", source_url=url,
            raw_path=raw_path, page=page, site_total_products=total, origin=origin,
            items=[RawProduct.from_item(item, extraction="listing_card") for item in items])


    def log_run(self, record: dict) -> None:
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        with self.run_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


    def scrape_category(self, category: str, pages: int, delay: float) -> dict:
        slug = CATEGORIES[category]
        run_date = date.today().isoformat()
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        all_items: list[dict] = []
        site_total = None

        for page in range(1, pages + 1):
            url = f"{BASE_URL}{slug}" if page == 1 else f"{BASE_URL}{slug}?page={page}"
            html, raw_path, origin = self.fetcher.fetch(url)
            items, total = self.listing_parser.parse_listing(html)
            site_total = site_total or total
            self.save_items(category, page, items, total, url, raw_path, run_date, origin=origin)
            all_items.extend(items)
            print(f"  {category} page {page}: {len(items):>3} items (site total {total})", flush=True)


        record = {
            "shop": SHOP["name"],
            "category": category,
            "pages_fetched": pages,
            "items_found": len(all_items),
            "site_total_products": site_total,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "ok" if all_items else "partial",
        }
        self.log_run(record)
        return record


    def run(self) -> int:
        failed = False
        try:
            grand_total = 0
            for category in self.categories:
                print(f"[{category}] {BASE_URL}{CATEGORIES[category]}", flush=True)
                try:
                    record = self.scrape_category(category, self.pages, self.delay)
                    grand_total += record["items_found"]
                    failed = failed or record["status"] != "ok"
                except (requests.RequestException, OSError, ValueError) as exc:
                    failed = True
                    print(f"  Collection error: {exc}", file=sys.stderr)
                    self.log_run({
                        "shop": SHOP["name"], "category": category, "pages_fetched": 0,
                        "items_found": 0, "status": "failed", "note": str(exc),
                        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    })

            print(f"\ntotal items scraped: {grand_total}")
            return 1 if failed else 0
        finally:
            self.fetcher.close()


def save_items(category: str, page: int, items: list[dict], total: int | None,
               url: str, raw_path: Path, run_date: str) -> Path:
    """Compatibility entry point for existing callers."""
    worker = DatatronicScraper([])
    try:
        return worker.save_items(category, page, items, total, url, raw_path, run_date)
    finally:
        worker.fetcher.close()


def log_run(record: dict) -> None:
    """Compatibility entry point for existing callers."""
    worker = DatatronicScraper([])
    try:
        worker.log_run(record)
    finally:
        worker.fetcher.close()


def scrape_category(session: PageFetcher, category: str, pages: int, delay: float) -> dict:
    """Preserve the caller-owned fetcher's lifetime for the original function."""
    return DatatronicScraper([category], pages, delay, fetcher=session).scrape_category(category, pages, delay)


