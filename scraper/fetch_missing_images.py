"""Fetch the product pages whose pictures are still missing from the catalogue.

The listing pages did not carry a picture for 314 catalogue rows (120 of them graphics
cards). Their product pages were never downloaded, so `og:image` cannot be read from the
cache for them. This run fetches only those pages, through the same rate-limited,
robots-checked fetcher the spec crawl uses, and writes them to the same cache shape.
"""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scraper.common.fetching import PageFetcher          # noqa: E402
from scraper.pipeline import images                      # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT / "data/raw/html/specs"


def main() -> int:
    rows = json.loads((ROOT / "data/normalised/components.json").read_text())["components"]
    listing = images.load(ROOT / "data/normalised/images.json")
    products = images.load(ROOT / "data/normalised/images_from_product_pages.json")

    targets: list[str] = []
    seen: set[str] = set()
    for component in rows:
        if images.image_for(component, listing, products):
            continue
        for entry in component.get("listings") or []:
            url = entry.get("url")
            if not url or "datatronic.fi" not in url:
                continue
            key = images.url_key(url)
            if key in seen:
                break
            seen.add(key)
            targets.append(url)
            break

    print(f"pages to fetch: {len(targets)}")
    fetcher = PageFetcher(CACHE, "datatronic", {"datatronic.fi"}, delay=1.2)
    ok = failed = cached = 0
    try:
        for index, url in enumerate(targets, 1):
            try:
                _html, _path, origin = fetcher.fetch(url)
                if origin == "cache":
                    cached += 1
                else:
                    ok += 1
            except Exception as exc:                     # noqa: BLE001 - report and continue
                failed += 1
                print(f"  fail {url}: {exc}", file=sys.stderr)
            if index % 25 == 0:
                print(f"  {index}/{len(targets)}  fetched {ok}, cached {cached}, failed {failed}")
    finally:
        fetcher.close()
    print(f"done: fetched {ok}, from cache {cached}, failed {failed} of {len(targets)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
