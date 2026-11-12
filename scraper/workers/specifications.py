"""Datatronic product specification collection, caching and checkpoints."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests
from scraper.config import PROJECT_ROOT, CATEGORIES, RAW_DIR as DEFAULT_RAW_DIR, NORMALISED_DIR as DEFAULT_OUT_DIR
from scraper.common.fetching import PageFetcher
from scraper.retailers.datatronic_specs import DatatronicSpecParser, FIELD_MAP
from scraper.pipeline.reports import SpecificationReportWriter

CACHE_DIR = PROJECT_ROOT / "data" / "raw" / "html" / "specs"


def iter_listings(raw_dir: Path, categories: Optional[List[str]]) -> List[Dict[str, str]]:
    """Every product URL found in data/raw/*.json, with its category and shop."""
    seen: Dict[str, Dict[str, str]] = {}
    for path in sorted(raw_dir.glob("*.json")):
        if path.name in {"scrape_runs.jsonl"}:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or "items" not in payload:
            continue
        category = payload.get("category")
        shop = payload.get("shop", "?")
        if shop.casefold() != "datatronic":
            continue
        if category is None or (categories and category not in categories):
            continue
        for item in payload["items"]:
            url = item.get("url")
            if not url or url in seen:
                continue
            seen[url] = {"url": url, "category": category, "name": item.get("name", ""),
                         "external_id": str(item.get("external_id") or ""), "shop": shop}
    return list(seen.values())


def cache_path(url: str, external_id: str, run_date: str) -> Path:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return CACHE_DIR / "datatronic" / run_date / f"{key}.html"


def fetch_page(fetcher: PageFetcher, url: str) -> Tuple[str, str]:
    """Use the shared robots, host validation, cache and request-spacing policy."""
    html, _, origin = fetcher.fetch(url)
    return html, origin


def load_store(path: Path) -> Dict[str, Any]:
    if path.exists():
        try:
            store = json.loads(path.read_text(encoding="utf-8"))
            store.setdefault("items", {})
            return store
        except json.JSONDecodeError:
            pass
    return {"generated_at": date.today().isoformat(),
            "source": "Datatronic product pages (data sheet)",
            "items": {}}


def write_store(path: Path, store: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    store["generated_at"] = date.today().isoformat()
    store["item_count"] = len(store["items"])
    path.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


class DatatronicSpecExtractor:
    """Own a specification pass, its shared fetcher and retailer-specific parser.

    Pure unit conversion helpers stay functions. The extractor keeps the existing
    checkpoint, report, cache, incremental and offline-reparse behaviour.
    Missing/empty results and request or parser failures return a nonzero status.
    """

    def __init__(self, options: argparse.Namespace, session=None,
                 spec_parser: DatatronicSpecParser | None = None, report_writer=None,
                 fetcher: PageFetcher | None = None):
        self.options = options
        if fetcher is not None and session is not None:
            raise ValueError("supply a fetcher or a session, not both")
        self.fetcher = fetcher if fetcher is not None else PageFetcher(
            CACHE_DIR, "datatronic", {"datatronic.fi", "www.datatronic.fi"},
            delay=options.delay, offline=options.reparse, force=options.force, session=session)
        self.session = self.fetcher.session
        self.spec_parser = spec_parser or DatatronicSpecParser()
        self.report_writer = report_writer if report_writer is not None else SpecificationReportWriter(FIELD_MAP)

    def run(self) -> int:
        """Close the session on success, status-only exits and failures alike."""
        try:
            return self._run()
        finally:
            self.fetcher.close()

    def _run(self) -> int:
        if self.options.status:
            store = load_store(self.options.out / "specs.json")
            items = store.get("items", {})
            if not items:
                print("specs.json is empty — run the extractor first", file=sys.stderr)
                return 1
            by_category: Dict[str, List[Dict[str, Any]]] = {}
            for entry in items.values():
                by_category.setdefault(entry.get("category", "?"), []).append(entry)
            print(f"specs.json — {len(items)} products ({store.get('generated_at')})")
            for category in CATEGORIES:
                entries = by_category.get(category)
                if not entries:
                    continue
                print(f"\n[{category}] {len(entries)} products, "
                      f"{sum(1 for e in entries if e.get('status') == 'ok')} parsed ok")
                for field in FIELD_MAP.get(category, {}):
                    found = sum(1 for e in entries if (e.get("specs") or {}).get(field) is not None)
                    pct = round(100 * found / len(entries))
                    mark = "  " if pct == 0 else ("!!" if pct < 40 else "ok")
                    print(f"   {mark} {field:24} {found:>3}/{len(entries):<3} {pct:>3}%")
            print(f"\nreport: {self.report_writer.write(self.options.out, store)}")
            return 0

        listings = iter_listings(self.options.raw_dir, self.options.category)
        if not listings:
            print("no listings found — run python3 -m scraper collect --shop datatronic --all first", file=sys.stderr)
            return 1
        if self.options.limit:
            listings = listings[:self.options.limit]

        store_path = self.options.out / "specs.json"
        store = load_store(store_path)
        run_date = date.today().isoformat()

        done = parsed_ok = skipped = failed = no_cache = 0
        started = time.monotonic()
        print(f"{len(listings)} products to read (cache: {self.fetcher.cache_dir})", flush=True)

        for listing in listings:
            url = listing["url"]
            existing = store["items"].get(url)

            # A previous run is reusable only when it actually parsed fields.
            if not self.options.reparse and existing and existing.get("status") == "ok" \
                    and existing.get("specs") and not self.options.force \
                    and str(existing.get("fetched_at", "")).startswith(run_date):
                skipped += 1
                continue
            try:
                html, origin = fetch_page(self.fetcher, url)
            except (requests.RequestException, OSError, ValueError) as exc:
                if isinstance(exc, FileNotFoundError) and self.options.reparse:
                    # An offline miss is a failed run, not a new failed observation.
                    # Keep any previously collected specs intact.
                    no_cache += 1
                    print(f"  NO CACHE {url} — {exc}", file=sys.stderr, flush=True)
                    continue
                failed += 1
                store["items"][url] = {
                    "category": listing["category"], "name": listing["name"],
                    "external_id": listing["external_id"], "shop": listing["shop"],
                    "specs": {}, "status": "failed", "error": str(exc)[:120],
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source": "product_page",
                }
                print(f"  [{listing['category']:11}] FAILED {url} — {exc}", file=sys.stderr, flush=True)
                continue

            try:
                features, method = self.spec_parser.extract_features(html)
                specs, unmapped = self.spec_parser.parse_specs(listing["category"], features)
                store["items"][url] = {
                    "category": listing["category"],
                    "name": listing["name"],
                    "external_id": listing["external_id"],
                    "shop": listing["shop"],
                    "specs": specs,
                    "spec_count": len(specs),
                    "feature_count": len(features),
                    "extraction": method,
                    "unmapped": unmapped,
                    "status": "ok" if specs else "empty",
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source": "product_page",
                    "origin": origin,
                }
                if specs:
                    parsed_ok += 1
                else:
                    failed += 1
                    store["items"][url]["error"] = "no supported specification fields parsed"
                print(f"  [{listing['category']:11}] {len(specs):>2} specs / {len(features):>2} fields "
                      f"· {listing['name'][:52]}", flush=True)
                done += 1
            except Exception as exc:  # parsing must never kill a long run
                failed += 1
                store["items"][url] = {
                    "category": listing["category"], "name": listing["name"],
                    "external_id": listing["external_id"], "shop": listing["shop"],
                    "specs": {}, "status": "failed", "error": f"{type(exc).__name__}: {exc}"[:120],
                    "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "source": "product_page",
                }
                print(f"  [{listing['category']:11}] PARSE FAILED {listing['name'][:40]} — {exc}",
                      file=sys.stderr, flush=True)

            if done and done % self.options.checkpoint_every == 0:
                write_store(store_path, store)
                elapsed = time.monotonic() - started
                print(f"  … checkpoint: {done} fetched, {parsed_ok} parsed, {skipped} skipped, "
                      f"{failed} failed ({elapsed/60:.1f} min)", flush=True)

        write_store(store_path, store)
        report = self.report_writer.write(self.options.out, store)

        print(f"\nfetched {done} pages ({skipped} already done today, {no_cache} not in cache, "
              f"{failed} failed)")
        print(f"parsed specs for {parsed_ok} products → {store_path}")
        print(f"report → {report}")
        return 1 if failed or no_cache else 0


def write_report(out_dir: Path, store: Dict[str, Any]) -> Path:
    """Compatibility function; delegate report rendering to its writer."""
    return SpecificationReportWriter(FIELD_MAP).write(out_dir, store)
