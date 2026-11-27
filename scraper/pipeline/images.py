"""Product images, recovered from the listing pages we already downloaded.

The listing crawler saves every category page, and each card on those pages carries the
product's thumbnail URL next to its shop id — so images cost **no extra requests**. This
module only reads `data/raw/html/*.html` and writes `data/normalised/images.json`
(shop external id -> image URL).

PrestaShop (Datatronic) writes `data-id-product="170849"` and inside the same card an
`<img src = "https://datatronic.fi/1166544-home_default/<slug>.jpg">`. Two details the
scraper must respect, both learned from the saved pages: the shop puts **spaces around
`=`** in attributes, and the image can be in a lazy-loading attribute instead of `src`.

The slug inside the image URL repeats the product name, which is what makes the result
checkable: `python3 -m scraper images` prints how many ids were found, and the URL for a
sample can be compared against the row's `raw_name` without opening a browser.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

CARD_ID = re.compile(r'data-id-product\s*=\s*"(\d+)"')
IMAGE_ATTRIBUTES = (
    re.compile(r'\bsrc\s*=\s*"([^"]+)"'),
    re.compile(r'\bdata-src\s*=\s*"([^"]+)"'),
    re.compile(r'\bdata-srcset\s*=\s*"([^"\s,]+)'),
)
NOT_A_PRODUCT_IMAGE = re.compile(r"(data:image|blank\.gif|grey\.gif|placeholder|/img/)", re.I)

# --- product pages -----------------------------------------------------------------------
# The listing pages do not always carry a picture (a card laid out differently, a second
# page of the category), which left 307 catalogue rows without an image — 120 of them
# graphics cards, the category where a missing photo is most obvious. Every *product* page
# we already downloaded for the spec sheets names both itself and its picture, so those
# gaps can be filled from the cache at **no extra request**:
#
#   <link rel="canonical" href="https://datatronic.fi/komponentit/kotelot/<slug>">
#   property="og:image" content="https://datatronic.fi/629824-large_default/<slug>.jpg"
#
# The advertised file is the large variant; the list shows a 56 px thumbnail, and
# PrestaShop serves the same file in other sizes by changing the type in the URL, so
# `-large_default/` is rewritten to `-home_default/`.
CANONICAL = re.compile(r'<link\s+rel\s*=\s*"canonical"\s+href\s*=\s*"([^"]+)"', re.I)
PRODUCT_IMAGE = re.compile(r'property\s*=\s*"og:image"\s+content\s*=\s*"([^"]+)"', re.I)
LARGE_VARIANT = re.compile(r"-[a-z]+_default/")


def thumb_variant(url: str) -> str:
    """The small size of the shop's own picture, for the same file in the same folder."""
    return LARGE_VARIANT.sub("-home_default/", url)


def url_key(url: str) -> str:
    """Shop URLs differ in query strings and a trailing slash; compare them without."""
    return re.sub(r"[?#].*$", "", str(url or "")).strip().rstrip("/")

# A card ends where the next one begins; the cap keeps a stray id (a hidden input, a
# suggestion) from pairing with a neighbour's picture.
MAX_CARD_CHARS = 6000


def image_in_card(card: str) -> str | None:
    for attribute in IMAGE_ATTRIBUTES:
        for match in attribute.finditer(card):
            url = match.group(1)
            if url.startswith("http") and not NOT_A_PRODUCT_IMAGE.search(url):
                return url
    return None


def images_from_page(html: str) -> dict[str, str]:
    """id -> image URL for one cached listing page; later cards win a duplicate id."""
    found: dict[str, str] = {}
    cards = list(CARD_ID.finditer(html))
    for index, card in enumerate(cards):
        start = card.start()
        end = cards[index + 1].start() if index + 1 < len(cards) else start + MAX_CARD_CHARS
        url = image_in_card(html[start:min(end, start + MAX_CARD_CHARS)])
        if url:
            found[card.group(1)] = url
    return found


def extract(html_dir: Path, out_path: Path, pattern: str = "*.html") -> dict:
    pages = sorted(html_dir.glob(pattern))
    merged: dict[str, str] = {}
    used = 0
    for page in pages:
        try:
            found = images_from_page(page.read_text(errors="replace"))
        except OSError as exc:
            print(f"  skip {page.name}: {exc}", file=sys.stderr)
            continue
        if found:
            used += 1
            merged.update(found)
    payload = {
        "source": "cached listing pages",
        "captured": date.today().isoformat(),
        "pages": used,
        "images": dict(sorted(merged.items())),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def extract_product_pages(html_dir: Path, out_path: Path, pattern: str = "*.html") -> dict:
    """`url -> image URL` for cached product pages, keyed by the page's own canonical URL."""
    pages = sorted(html_dir.glob(pattern))
    merged: dict[str, str] = {}
    used = 0
    for page in pages:
        try:
            html = page.read_text(errors="replace")
        except OSError as exc:
            print(f"  skip {page.name}: {exc}", file=sys.stderr)
            continue
        canonical = CANONICAL.search(html)
        image = PRODUCT_IMAGE.search(html)
        if not (canonical and image):
            continue
        picture = image.group(1).strip()
        # An empty og:image means the shop publishes no picture for the product; a row
        # stays without one rather than borrowing a neighbour's (see the report in the PR).
        if not picture or NOT_A_PRODUCT_IMAGE.search(picture):
            continue
        merged[url_key(canonical.group(1))] = thumb_variant(picture)
        used += 1
    payload = {
        "source": "cached product pages (og:image)",
        "captured": date.today().isoformat(),
        "pages": used,
        "images": dict(sorted(merged.items())),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load(path: Path) -> dict[str, str]:
    """The saved map, or an empty one: a missing file means "no images yet", not a crash."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("images", {})
    except (OSError, json.JSONDecodeError):
        return {}


def image_for(component: dict, images: dict[str, str], product_pages: dict[str, str] | None = None) -> str | None:
    """A component's image: the first listing whose shop id has one, and if none does, the
    first listing whose product page we cached a picture for."""
    for listing in component.get("listings") or []:
        url = images.get(str(listing.get("external_id")))
        if url:
            return url
    for listing in component.get("listings") or []:
        url = (product_pages or {}).get(url_key(listing.get("url")))
        if url:
            return url
    return None
