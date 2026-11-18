"""Catalogue export and complete-content drift checking.

`data/normalised/components.json` is the reviewed pipeline artefact: it carries per-field
provenance (`spec_sources`, ~35% of the file), `missing_specs` and `category_confidence`.
None of that is read by the app, and the full catalogue is ~12x the size of the first
335-component version, so the deployment copy is deliberately slimmer and minified:

  * only the fields the app reads: category, brand, model, raw_name, specs, listings
  * `spec_source` + `spec_fields` instead of the per-field provenance map
  * only non-empty spec values (the app's `has()` / `known()` treat absent and null alike)
  * minified JSON — it is machine-read; the pretty version is the pipeline artefact

Measured on the 335-component catalogue: 475 KB -> 228 KB. The copy is also the one thing
that can drift: the deployed site kept showing name-only specs for two days after the
data-sheet work landed, so `--check` compares it byte for byte against what this module
would write, which catches both a stale copy and a hand-edited one.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from scraper.config import PROJECT_ROOT

SOURCE = PROJECT_ROOT / "data" / "normalised" / "components.json"
TARGET = PROJECT_ROOT / "web" / "data" / "components.json"

# Fields the web app shows as "we could not check" when they are missing.
KEY_FIELDS = ("power_w", "recommended_psu_w", "length_mm", "tdp_w", "socket",
              "wattage_w", "max_gpu_length_mm", "memory_type")

# Fields the app reads from a listing (web/lib/catalog.js -> toComponent).
LISTING_FIELDS = ("shop", "url", "external_id", "price_cents", "in_stock", "snapshot_date")


def load(path: Path) -> dict:
    if not path.exists():
        print(f"missing {path} — run: python3 -m scraper normalise", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def parsed_fields(component: dict) -> set[str]:
    """The fields whose value came from the manufacturer's product page.

    `spec_sources` maps a field to a provenance string, e.g.
    `{"socket": "parsed_product_page", "memory_type": "inferred_chipset"}`.
    """
    sources = component.get("spec_sources") or {}
    return {field for field, source in sources.items()
            if isinstance(source, str) and source.startswith("parsed")}


def parsed_count(payload: dict) -> int:
    """Components carrying at least one value parsed from a product page.

    The pipeline artefact records this per field; a web copy declares it as a count,
    because the per-field map is what the slimming removes.
    """
    if payload.get("parsed_specs") is not None:
        return int(payload["parsed_specs"])
    return sum(1 for component in payload.get("components", []) if parsed_fields(component))


def slim(component: dict) -> dict:
    """One component in the shape the app reads, with the empty values dropped."""
    specs = {field: value for field, value in (component.get("specs") or {}).items()
             if value not in (None, "", [])}
    listings = [{key: listing.get(key) for key in LISTING_FIELDS
                 if listing.get(key) is not None}
                for listing in component.get("listings") or []]
    slimmed = {
        "category": component.get("category"),
        "brand": component.get("brand"),
        "model": component.get("model"),
        "raw_name": component.get("raw_name"),
        "specs": specs,
        "listings": listings,
    }
    from_page = parsed_fields(component)
    if from_page:
        slimmed["spec_source"] = "product_page"
        slimmed["spec_fields"] = len(from_page)
    return slimmed


def has_current_price(component: dict) -> bool:
    """A price is what makes a row usable: the picker shows one part per row with its
    cost, and 50 rows on the full catalogue had a listing without a price at all."""
    return any((listing.get("price_cents") or 0) > 0
               for listing in component.get("listings") or [])


def build_web_copy(payload: dict) -> dict:
    """The exact payload written to web/data/components.json."""
    components = [slim(component) for component in payload.get("components", [])
                  if has_current_price(component)]
    return {
        "generated_at": payload.get("generated_at"),
        "source": payload.get("source"),
        "component_count": len(components),
        "parsed_specs": sum(1 for c in components if c.get("spec_source") == "product_page"),
        "components": components,
    }


def render(payload: dict) -> bytes:
    """The bytes of the deployment copy — minified, because only machines read it."""
    return json.dumps(build_web_copy(payload), ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def summarise(payload: dict) -> str:
    components = payload.get("components", [])
    parsed = parsed_count(payload)
    fields: dict[str, int] = {}
    for component in components:
        for field, value in (component.get("specs") or {}).items():
            if value not in (None, [], "") and field in KEY_FIELDS:
                fields[field] = fields.get(field, 0) + 1
    lines = [
        f"  components: {len(components)} (generated_at {payload.get('generated_at')})",
        f"  with product-page specs: {parsed}",
    ]
    for field in KEY_FIELDS:
        if field in fields:
            lines.append(f"    {field}: {fields[field]}")
    return "\n".join(lines)


class CatalogueExporter:
    """Own the catalogue source and deployment copy, including drift checking."""

    def __init__(self, source: Path | None = None, target: Path | None = None,
                 project_root: Path | None = None):
        self.source = SOURCE if source is None else source
        self.target = TARGET if target is None else target
        self.project_root = PROJECT_ROOT if project_root is None else project_root

    def run(self, check: bool = False) -> int:
        source = load(self.source)
        print("source  data/normalised/components.json")
        print(summarise(source))

        # The copy is machine-produced, so freshness is a byte-for-byte question: if it
        # differs from what this module would write, the pipeline moved on or someone
        # edited the copy by hand.
        expected = render(source)

        if check:
            if not self.target.exists():
                print(f"web copy missing: {self.target}", file=sys.stderr)
                return 1
            actual = self.target.read_bytes()
            if actual == expected:
                print("target  web/data/components.json")
                print(summarise(load(self.target)))
                print(f"\nweb copy is up to date ({len(actual) / 1024:.0f} KB)")
                return 0
            target = load(self.target)
            print("target  web/data/components.json")
            print(summarise(target))
            reasons = []
            if source.get("generated_at") != target.get("generated_at"):
                reasons.append(f"generated_at {target.get('generated_at')} != {source.get('generated_at')}")
            if source.get("component_count") != target.get("component_count"):
                reasons.append(f"component_count {target.get('component_count')} != {source.get('component_count')}")
            if parsed_count(source) != parsed_count(target):
                reasons.append(f"parsed specs {parsed_count(target)} != {parsed_count(source)}")
            detail = "; ".join(reasons) or "content differs (a value was edited by hand, or the pipeline moved on)"
            print(f"\nweb copy is STALE — {detail}")
            print("run without --check to refresh")
            return 1

        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_bytes(expected)
        display = self.target.relative_to(self.project_root) if self.target.is_relative_to(self.project_root) else self.target
        published = build_web_copy(source)["components"]
        dropped = sum(1 for component in source.get("components", []) if not has_current_price(component))
        per_component = len(expected) / max(len(published), 1)
        print(f"\nwrote {display} — {len(expected) / 1024:.0f} KB ({per_component:.0f} B/component)")
        if dropped:
            print(f"  dropped {dropped} components without a priced listing "
                  f"(they stay in data/normalised/)")
        print(f"  extrapolated for a full catalogue: {per_component * 3945 / 1024 / 1024:.1f} MB")
        print("commit it — Vercel deploys from the repository, so an uncommitted copy "
              "does not reach the deployed site")
        return 0
