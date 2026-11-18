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


def load(path: Path) -> dict[str, str]:
    """The saved map, or an empty one: a missing file means "no images yet", not a crash."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("images", {})
    except (OSError, json.JSONDecodeError):
        return {}


def image_for(component: dict, images: dict[str, str]) -> str | None:
    """A component's image: the first listing whose shop id has one."""
    for listing in component.get("listings") or []:
        url = images.get(str(listing.get("external_id")))
        if url:
            return url
    return None
