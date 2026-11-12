#!/usr/bin/env python3
"""BuildWise data worker — Jimms product-page price proof.

Reads a small, explicit URL manifest rather than crawling JS-rendered listings.
Writes the same category/item payload consumed by the existing normaliser.

Usage:
    python scraper/scrape_jimms.py --input jimms_urls.json
    python scraper/scrape_jimms.py --input jimms_urls.json --offline
    python scraper/scrape_jimms.py --input jimms_urls.json --force --delay 1.2

Etiquette:
    * one request at a time, at least one second between attempts
    * identified User-Agent, 30-second timeout, no automatic retries
    * successful HTML cached per retailer, URL and day
    * failures reported separately; a partial run exits non-zero
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from common.fetching import PageFetcher
from retailers.jimms import HOSTS, SHOP, parse_product

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATEGORIES = {"gpu", "cpu", "motherboard", "memory", "storage", "psu", "case"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Jimms product-page names and prices.")
    parser.add_argument("--input", required=True, type=Path, help="JSON list of category/url objects")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data",
                        help="output data directory; use a temporary directory for validation")
    parser.add_argument("--delay", type=float, default=1.0)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="only read today's cached HTML")
    mode.add_argument("--force", action="store_true", help="refetch today's cached pages")
    args = parser.parse_args()
    if not math.isfinite(args.delay) or args.delay < 1:
        parser.error("delay must be a finite number >= 1.0")
    try:
        manifest = json.loads(args.input.read_text(encoding="utf-8"))
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
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    raw_dir = args.data_dir / "raw"
    fetcher = PageFetcher(raw_dir / "html", "jimms", HOSTS,
                          args.delay, args.offline, args.force)
    # Validate every URL before the first request or output write.
    try:
        for entry in manifest:
            fetcher.validate_url(entry["url"])
    except ValueError as exc:
        fetcher.close()
        parser.error(str(exc))

    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%S%fZ")
    groups: dict[str, list] = {}
    failures = []
    try:
        for entry in manifest:
            url, category = entry["url"], entry["category"]
            try:
                html, path, origin = fetcher.fetch(url)
                product = parse_product(html)
                # Cache reuse must not pretend to be a new price observation.
                observed = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
                item = {**product, "url": url, "external_id": None}
                groups.setdefault(category, []).append((item, path, origin, observed))
                print(f"  [{category}] {product['name']} — {product['price_cents'] / 100:.2f} EUR ({origin})")
            except (requests.RequestException, OSError, ValueError) as exc:
                failures.append({"url": url, "category": category, "error": str(exc)})
                print(f"  FAILED {url} — {exc}", file=sys.stderr)
    finally:
        fetcher.close()

    raw_dir.mkdir(parents=True, exist_ok=True)
    # One product per payload preserves its own fetch timestamp and HTML source.
    for category, products in groups.items():
        for page, (item, path, origin, observed) in enumerate(products, 1):
            payload = {"shop": SHOP, "category": category, "page": page,
                       "source_url": item["url"], "fetched_at": observed,
                       "site_total_products": None, "items_on_page": 1,
                       "raw_html": str(path.relative_to(args.data_dir)),
                       "origin": origin, "items": [item]}
            target = raw_dir / f"jimms_{category}_p{page}_{run_id}.json"
            target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    record = {"shop": SHOP, "started_at": started.isoformat(timespec="seconds"),
              "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "items_found": sum(map(len, groups.values())), "failures": failures,
              "status": "partial" if failures and groups else "failed" if failures else "ok"}
    with (raw_dir / "scrape_runs.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"{record['status']}: {record['items_found']} products, {len(failures)} failures")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
