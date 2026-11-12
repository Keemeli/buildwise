"""Read retailer observations, merge components and write the catalogue."""
from __future__ import annotations
import json
from copy import deepcopy
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from scraper.config import PROJECT_ROOT, RAW_DIR as DEFAULT_RAW_DIR, NORMALISED_DIR as DEFAULT_OUT_DIR
from scraper.pipeline.components import (CATEGORIES, EXPECTED_FIELDS, clean,
    is_non_component, normalise_item, ComponentNameParser)
from scraper.pipeline.reports import NormalisationReportWriter
from scraper.pipeline.listing_prices import ListingPriceSelector
from scraper.pipeline.identity_matching import ProductIdentityMatcher, VerifiedProductGrouper


def iter_raw_items(raw_dir: Path, only_category: Optional[str]) -> List[Dict[str, Any]]:
    """Read every scraped payload in raw_dir, whatever shop produced it.

    File name convention is <shop>_<category>_p<n>_<date>.json, so any future
    scraper (Proshop, Jimms) is picked up without changing this function.
    """
    items: List[Dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            continue
        category = payload.get("category")
        if not category or (only_category and category != only_category):
            continue
        for item in payload.get("items", []):
            items.append({
                "category": category,
                "raw_name": clean(item.get("name") or ""),
                "price_cents": item.get("price_cents"),
                "url": item.get("url"),
                "external_id": item.get("external_id"),
                "retailer_sku": item.get("retailer_sku"),
                "identity": item.get("identity"),
                "shop": payload.get("shop", "Datatronic"),
                "fetched_at": payload.get("fetched_at") or "",
                "snapshot_date": (payload.get("fetched_at") or "")[:10] or "",
                "source_file": path.name,
                "provenance": {"source_file": path.name, **{key: payload.get(key) for key in
                    ("source_type", "source_url", "raw_html", "origin", "run_id")},
                    "extraction": item.get("extraction")},
            })
    return items


def dedupe(components: List[Dict[str, Any]], identity_report=None) -> Tuple[List[Dict[str, Any]], int]:
    """Collapse source snapshots and group only identifier-confirmed listings."""
    if identity_report is None:
        inputs = [{**item, 'listings': [item['listing']]} for item in components]
        identity_report = VerifiedProductGrouper().plan(ProductIdentityMatcher().build_report(inputs))
    memberships = {}
    group_details = {}
    for group_index, group in enumerate(identity_report['groups']):
        for position in group['listings']:
            listing = identity_report['listings'][position]
            memberships[(listing['shop'], listing['url'])] = group_index
        group_details[group_index] = group
    grouped = defaultdict(list)
    for component in components:
        listing = component['listing']
        group_index = memberships[(listing['shop'].casefold(), listing['url'])]
        # A malformed source assigning a URL to multiple categories cannot cross
        # category boundaries, even within that listing's historical snapshots.
        grouped[(component['category'], group_index)].append(component)
    selector = ListingPriceSelector()
    output = []
    for (_, group_index), entries in sorted(grouped.items()):
        representative = max(entries, key=lambda item: (
            len(item['specs']) - len(item['missing_specs']),
            selector.observed_at(item['listing']), json.dumps(item, sort_keys=True)))
        component = deepcopy(representative)
        component.pop('listing')
        by_listing = defaultdict(list)
        for entry in entries:
            listing = entry['listing']
            by_listing[(listing['shop'].casefold(), listing['url'])].append(listing)
        component['listings'] = [selector.select(rows) for _, rows in sorted(by_listing.items())]
        group = group_details[group_index]
        component['identity_match'] = {'status': group['status'], 'reasons': group['reasons']}
        output.append(component)
    return output, len(components) - len(output)


def shape_modules(components: List[Dict[str, Any]]) -> int:
    """The web UI shows memory as '32 GB (2×16 GB)', reading `modules.count` and
    `modules.size_gb`. The pipeline stores `modules` as a plain count, so the shape is
    built here from the two values we already have rather than left for the UI to guess
    (it rendered 'undefined×undefined GB' when the shape did not match).
    """
    shaped = 0
    for component in components:
        specs = component["specs"]
        count = specs.get("modules")
        capacity = specs.get("capacity_gb")
        if component["category"] == "memory" and isinstance(count, int) and count > 0 and capacity:
            specs["modules"] = {"count": count, "size_gb": round(capacity / count)}
            shaped += 1
    return shaped


def retain_product_identity_evidence(components, path):
    """Attach source observations to listings without selecting a match or ID."""
    if not path.exists():
        return
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return
    by_url = {}
    for url, entry in payload.get('items', {}).items():
        for observed in (entry, entry.get('last_attempt', {})):
            identity = observed.get('identity')
            if not isinstance(identity, dict) or not observed.get('fetched_at'):
                continue
            by_url.setdefault(url, []).append({
                'identity': identity, 'shop': observed.get('shop', entry.get('shop')),
                'listing_url': url, 'source_url': url, 'source_type': 'product',
                'raw_html': observed.get('raw_html'), 'fetched_at': observed['fetched_at'],
                'origin': observed.get('origin'),
            })
    for component in components:
        for listing in component['listings']:
            observations = list(listing.get('identity_observations', []))
            observations.extend(source for source in by_url.get(listing['url'], [])
                                if str(source.get('shop', '')).casefold() == listing['shop'].casefold())
            if observations:
                unique = {json.dumps(source, sort_keys=True): source for source in observations}
                listing['identity_observations'] = [unique[key] for key in sorted(unique)]


def load_product_specs(path: Path) -> Dict[str, Dict[str, Any]]:
    """Shared specs.json from retailer specification collection, keyed by product URL."""
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {url: entry for url, entry in payload.get("items", {}).items()
            if entry.get("status") == "ok" and entry.get("specs")}


def merge_product_specs(components: List[Dict[str, Any]],
                        specs_path: Path) -> Dict[str, int]:
    """Overwrite name-derived values with values parsed from the product page.

    A parsed value always wins over a guessed one, but the provenance is kept:
    Contradictory product-page values stay null with their source evidence.
    Every field that came from a data sheet is recorded in `spec_sources`, and the
    CPU `socket_source` stops saying "inferred" once a real socket was read.
    """
    specs_by_url = load_product_specs(specs_path)
    stats = {"components_matched": 0, "fields_parsed": 0, "upgraded_from_inferred": 0,
             "sockets_parsed": 0, "gaps_closed": 0}
    if not specs_by_url:
        return stats

    for component in components:
        sources = component.setdefault("spec_sources", {})
        matched: Dict[str, Any] = {}
        candidates = defaultdict(list)
        for listing in component["listings"]:
            entry = specs_by_url.get(listing["url"])
            if not entry or (entry.get('shop') and entry['shop'].casefold() != listing['shop'].casefold()):
                continue
            if entry.get('category') and entry['category'] != component['category']:
                continue
            for field, value in entry['specs'].items():
                if value not in (None, [], ""):
                    candidates[field].append({'value': value, 'shop': listing['shop'],
                                              'url': listing['url'], 'raw_html': entry.get('raw_html'),
                                              'fetched_at': entry.get('fetched_at')})
        for field, observations in sorted(candidates.items()):
            values = {json.dumps(item['value'], sort_keys=True) for item in observations}
            if len(values) == 1:
                matched[field] = observations[0]['value']
                continue
            component['specs'][field] = None
            sources[field] = 'conflicting_product_pages'
            component.setdefault('spec_conflicts', {})[field] = sorted(
                observations, key=lambda item: json.dumps(item, sort_keys=True))
            if field in EXPECTED_FIELDS.get(component['category'], ()) and field not in component['missing_specs']:
                component['missing_specs'].append(field)
        if not candidates:
            continue
        stats["components_matched"] += 1

        for field, value in matched.items():
            if value in (None, [], ""):
                continue
            previous = component["specs"].get(field)
            # The normaliser records inference in a sibling field, e.g.
            # "socket_source": "inferred_from_sku" for a guessed CPU socket.
            previous_source = str(component["specs"].get(f"{field}_source", ""))
            if previous is not None and (previous_source.startswith("inferred")
                                         or sources.get(field, "").startswith("inferred")):
                stats["upgraded_from_inferred"] += 1
            if previous is None:
                if field in component.get("missing_specs", []):
                    component["missing_specs"] = [f for f in component["missing_specs"] if f != field]
                    stats["gaps_closed"] += 1
                stats["fields_parsed"] += 1
            component["specs"][field] = value
            sources[field] = "parsed_product_page"

        if matched.get("socket") and component["specs"].get("socket_source"):
            component["specs"]["socket_source"] = "parsed_product_page"
            stats["sockets_parsed"] += 1

    return stats


class ComponentNormaliser:
    """Build the multi-retailer catalogue from configured input/output paths.

    An optional item parser allows the name-normalisation strategy to be replaced
    without changing file collection, deduplication or product-spec merging.
    """

    def __init__(self, raw_dir: Path, out_dir: Path, category: str | None = None,
                 item_parser=None, report_writer=None):
        self.raw_dir = raw_dir
        self.out_dir = out_dir
        self.category = category
        self.name_parser = ComponentNameParser()
        self.normalise_item = self.name_parser.parse if item_parser is None else item_parser
        self.report_writer = report_writer if report_writer is not None else NormalisationReportWriter()

    def run(self) -> int:
        if not self.raw_dir.exists():
            print(f"no raw data at {self.raw_dir} — run python3 -m scraper collect --shop datatronic --all first", file=sys.stderr)
            return 1

        raw_items = iter_raw_items(self.raw_dir, self.category)
        if not raw_items:
            print("no items found in raw data", file=sys.stderr)
            return 1

        excluded = [item["raw_name"] for item in raw_items if is_non_component(item["raw_name"])]
        products = [item for item in raw_items if not is_non_component(item["raw_name"])]

        normalised = [self.normalise_item(item) for item in products]
        # Resolve identity and variant evidence per listing before grouping.
        identity_inputs = [deepcopy({**item, 'listings': [item['listing']]}) for item in normalised]
        retain_product_identity_evidence(identity_inputs, self.out_dir / "specs.json")
        merge_product_specs(identity_inputs, self.out_dir / "specs.json")
        identity_report = ProductIdentityMatcher().build_report(identity_inputs)
        identity_report = VerifiedProductGrouper().plan(identity_report)
        components, duplicates = dedupe(normalised, identity_report)
        retain_product_identity_evidence(components, self.out_dir / "specs.json")
        spec_stats = merge_product_specs(components, self.out_dir / "specs.json")
        spec_stats["modules_shaped"] = shape_modules(components)

        self.out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "source": ", ".join(sorted({item["shop"] for item in raw_items})),
            "component_count": len(components),
            "identity_policy_version": identity_report["policy_version"],
            "components": components,
        }
        identity_path = self.out_dir / "identity_matches.json"
        identity_path.write_text(json.dumps(identity_report, ensure_ascii=False, indent=2), encoding="utf-8")
        components_path = self.out_dir / "components.json"
        components_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        excluded_path = self.out_dir / "excluded_non_components.json"
        excluded_path.write_text(json.dumps({"excluded": excluded}, ensure_ascii=False, indent=2), encoding="utf-8")
        report_path = self.report_writer.write(self.out_dir, components, duplicates, len(raw_items), excluded, spec_stats)

        print(f"scanned {len(raw_items)} raw products → {len(components)} components "
              f"({duplicates} duplicates merged, {len(excluded)} non-components excluded)")
        print(f"wrote {components_path}")
        print(f"wrote {identity_path} (verified grouping and review cases)")
        print(f"wrote {excluded_path}")
        print(f"wrote {report_path}")

        by_category: Dict[str, int] = defaultdict(int)
        for component in components:
            by_category[component["category"]] += 1
        for category in CATEGORIES:
            if by_category.get(category):
                without_specs = sum(1 for c in components
                                    if c["category"] == category and len(c["missing_specs"]) == len(EXPECTED_FIELDS[category]))
                print(f"  {category:12} {by_category[category]:>3} components "
                      f"({without_specs} suspect: nothing parsed)")
        return 0


def write_report(out_dir, components, duplicates, scanned, excluded, spec_stats=None):
    """Compatibility function; report formatting belongs to its writer."""
    return NormalisationReportWriter().write(out_dir, components, duplicates, scanned, excluded, spec_stats)
