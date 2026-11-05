#!/usr/bin/env python3
"""BuildWise data worker — Datatronic category scraper.

Scrapes category listing pages, saves the raw HTML (so a later site change can be
debugged against real data) and writes a normalised JSON payload per category/page.

Usage:
    python scrape.py --category gpu --pages 2
    python scrape.py --all --pages 1
    python scrape.py --category gpu --pages 1 --delay 2.0

Etiquette (kept deliberately conservative):
    * one request at a time, `--delay` seconds apart (default 1.0)
    * identified User-Agent with a contact address
    * only category/listing URLs — never /api/, never the search endpoint
    * raw HTML cached on disk, one snapshot per day per page
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://datatronic.fi"
USER_AGENT = "BuildWise-course-project/0.1 (eekarjal24@students.oamk.fi)"

SHOP = {
    "name": "Datatronic",
    "domain": "datatronic.fi",
    "base_url": BASE_URL,
}

# verified 3.11.2026 — (slug on datatronic.fi, total products on the site)
CATEGORIES = {
    "gpu": "/naytonohjaimet",
    "cpu": "/prosessorit",
    "motherboard": "/emolevyt",
    "memory": "/muistit",
    "storage": "/kiintolevyt-ssd-levyt",
    "case": "/kotelot",
    "psu": "/virtalahteet",
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_HTML_DIR = PROJECT_ROOT / "data" / "raw" / "html"
RAW_JSON_DIR = PROJECT_ROOT / "data" / "raw"
RUN_LOG = PROJECT_ROOT / "data" / "raw" / "scrape_runs.jsonl"


def fetch(session: requests.Session, url: str) -> str:
    """One polite request. Raises for non-200."""
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def parse_price_cents(text: str) -> int | None:
    """'1 735,00 €' -> 173500. Returns None when no price is present."""
    if not text:
        return None
    cleaned = text.replace("\xa0", " ").replace("&nbsp;", " ")
    match = re.search(r"(\d[\d\s]{0,8},\d{2})\s*(?:€|&euro;|EUR)", cleaned)
    if not match:
        return None
    amount = match.group(1).replace(" ", "").replace(",", ".")
    return int(round(float(amount) * 100))


def parse_listing(html: str) -> tuple[list[dict], int | None]:
    """Parse the category listing container.

    The page also contains a 'featured products' block; only the container with
    id="js-product-list" holds the actual category results.
    """
    soup = BeautifulSoup(html, "html.parser")
    container = soup.find(id="js-product-list") or soup

    items: list[dict] = []
    for card in container.select("article.js-product-miniature, article.product-miniature"):
        name_el = card.select_one(".product-title a") or card.select_one("h3 a")
        link_el = card.select_one("a.js-product-image") or card.select_one("a[href]")
        price_el = card.select_one(".price")

        name = name_el.get_text(strip=True) if name_el else None
        href = link_el.get("href") if link_el else None
        price_cents = parse_price_cents(price_el.get_text(" ", strip=True) if price_el else "")

        if not name or not href:
            continue
        if href.startswith("/"):
            href = BASE_URL + href

        items.append(
            {
                "name": name,
                "price_cents": price_cents,
                "url": href,
                "external_id": card.get("data-id-product"),
            }
        )

    total = None
    total_match = re.search(r"Yhteensä\s*([\d\s]+)\s*tuotetta", soup.get_text(" ", strip=True))
    if total_match:
        total = int(total_match.group(1).replace(" ", ""))

    return items, total


def save_raw_html(html: str, category: str, page: int, run_date: str) -> Path:
    RAW_HTML_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(html.encode("utf-8")).hexdigest()[:12]
    path = RAW_HTML_DIR / f"datatronic_{category}_p{page}_{run_date}_{digest}.html"
    path.write_text(html, encoding="utf-8")
    return path


def save_items(category: str, page: int, items: list[dict], total: int | None, url: str, raw_path: Path, run_date: str) -> Path:
    RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "shop": SHOP["name"],
        "category": category,
        "page": page,
        "source_url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "site_total_products": total,
        "items_on_page": len(items),
        "raw_html": str(raw_path.relative_to(PROJECT_ROOT)),
        "items": items,
    }
    path = RAW_JSON_DIR / f"datatronic_{category}_p{page}_{run_date}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def log_run(record: dict) -> None:
    RAW_JSON_DIR.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def scrape_category(session: requests.Session, category: str, pages: int, delay: float) -> dict:
    slug = CATEGORIES[category]
    run_date = date.today().isoformat()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    all_items: list[dict] = []
    site_total = None

    for page in range(1, pages + 1):
        url = f"{BASE_URL}{slug}" if page == 1 else f"{BASE_URL}{slug}?page={page}"
        html = fetch(session, url)
        raw_path = save_raw_html(html, category, page, run_date)
        items, total = parse_listing(html)
        site_total = site_total or total
        save_items(category, page, items, total, url, raw_path, run_date)
        all_items.extend(items)
        print(f"  {category} page {page}: {len(items):>3} items (site total {total})", flush=True)
        if page < pages:
            time.sleep(delay)

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
    log_run(record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Datatronic category listings.")
    parser.add_argument("--category", choices=sorted(CATEGORIES), help="single category to scrape")
    parser.add_argument("--all", action="store_true", help="scrape every known category")
    parser.add_argument("--pages", type=int, default=1, help="how many listing pages per category")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    args = parser.parse_args()

    if not args.category and not args.all:
        parser.error("give --category <name> or --all")

    categories = sorted(CATEGORIES) if args.all else [args.category]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8"})

    grand_total = 0
    for category in categories:
        print(f"[{category}] {BASE_URL}{CATEGORIES[category]}", flush=True)
        try:
            record = scrape_category(session, category, args.pages, args.delay)
            grand_total += record["items_found"]
        except requests.HTTPError as exc:
            print(f"  HTTP error: {exc}", file=sys.stderr)
            log_run({
                "shop": SHOP["name"], "category": category, "pages_fetched": 0,
                "items_found": 0, "status": "failed", "note": str(exc),
                "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            })
        if len(categories) > 1:
            time.sleep(args.delay)

    print(f"\ntotal items scraped: {grand_total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())