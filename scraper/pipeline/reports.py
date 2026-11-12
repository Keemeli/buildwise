"""Coverage and review reports for catalogue and product specifications."""
from __future__ import annotations
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from scraper.config import CATEGORIES
from scraper.pipeline.components import EXPECTED_FIELDS, FACET_FIELDS


class NormalisationReportWriter:
    """Render coverage, exclusions and review candidates without collecting data."""

    def write(self, out_dir: Path, components: List[Dict[str, Any]], duplicates: int,
                     scanned: int, excluded: List[str],
                     spec_stats: Optional[Dict[str, int]] = None) -> Path:
        lines: List[str] = []
        lines.append(f"# Normalisation report — {date.today().isoformat()}")
        lines.append("")
        lines.append(f"Scanned {scanned} raw products from `data/raw/`, produced "
                     f"**{len(components)} unique components** ({duplicates} duplicate rows merged).")
        lines.append("")
        lines.append("Missing values are reported, not filled. A `null` spec means the shop's "
                     "product name does not contain that information.")
        lines.append("")

        lines.append("## Coverage per category")
        lines.append("")
        lines.append("| Category | Components | Field | Parsed | Coverage |")
        lines.append("|---|---|---|---|---|")
        by_category: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for component in components:
            by_category[component["category"]].append(component)

        for category in CATEGORIES:
            group = by_category.get(category, [])
            if not group:
                continue
            for field in EXPECTED_FIELDS.get(category, ()):
                found = sum(1 for c in group if c["specs"].get(field))
                pct = round(100 * found / len(group))
                lines.append(f"| {category} | {len(group)} | `{field}` | {found} | {pct}% |")
        lines.append("")

        # Facet vocabulary: the values a UI filter would offer. If the same real thing
        # appears in two spellings here, that is a data bug to fix in the pipeline, not a
        # comparison to special-case in the app.
        lines.append("## Facet vocabulary (values a UI filter would offer)")
        lines.append("")
        for category in CATEGORIES:
            for field in FACET_FIELDS.get(category, ()):
                counts: Dict[str, int] = defaultdict(int)
                for component in by_category.get(category, []):
                    value = component["specs"].get(field)
                    if value in (None, [], ""):
                        continue
                    for item in (value if isinstance(value, list) else [value]):
                        counts[str(item)] += 1
                if counts:
                    listed = ", ".join(f"{name} ×{count}" for name, count
                                       in sorted(counts.items(), key=lambda kv: -kv[1])[:6])
                    lines.append(f"- **{category}.{field}**: {listed}")
        lines.append("")

        if spec_stats and spec_stats.get("components_matched"):
            lines.append("## Values parsed from product pages (data sheet)")
            lines.append("")
            lines.append(f"- Components matched to a product page: **{spec_stats['components_matched']}**")
            lines.append(f"- Fields filled in from the data sheet: {spec_stats['fields_parsed']} "
                         f"({spec_stats['gaps_closed']} gaps in the name-based specs closed)")
            lines.append(f"- Guessed values replaced by parsed ones: {spec_stats['upgraded_from_inferred']}")
            lines.append(f"- CPU sockets now parsed instead of inferred: {spec_stats['sockets_parsed']}")
            lines.append("")
            lines.append("Each such field is recorded in the component's `spec_sources` as "
                         "`parsed_product_page`. It comes from the shop's own data sheet for that exact "
                         "product, not from the product name.")
            lines.append("")

        conflicts = [listing for component in components for listing in component['listings']
                     if listing.get('price_status') == 'conflict']
        if conflicts:
            lines.extend(['## Price conflicts requiring inspection', ''])
            for listing in conflicts:
                lines.append(f"- **{listing['shop']}** — {listing['url']} — current price unknown")
                for observation in listing['price_observations']:
                    lines.append(f"  - {observation['price_cents']} cents at {observation['fetched_at']} "
                                 f"— source: {observation.get('provenance')}")
            lines.append('')

        lines.append("## Products needing review (fewest specs found)")
        lines.append("")
        review = sorted(components, key=lambda c: (len(c["missing_specs"]), c["raw_name"]), reverse=True)[:15]
        for component in review:
            missing = ", ".join(component["missing_specs"]) or "none"
            lines.append(f"- **{component['category']}** — `{component['raw_name'][:80]}` — missing: {missing}")
        lines.append("")

        lines.append("## Rows excluded as non-components")
        lines.append("")
        lines.append(f"{len(excluded)} scraped rows were not hardware (assembly services or "
                     "accessories the shop lists inside a component category). They are kept in "
                     "`excluded_non_components.json` but must never reach the compatibility engine.")
        lines.append("")
        for name in excluded[:10]:
            lines.append(f"- `{name[:90]}`")
        lines.append("")

        suspects = [c for c in components if c.get("category_confidence") == "suspect"]
        if suspects:
            lines.append("## Suspect categories (nothing parsed at all)")
            lines.append("")
            for component in suspects[:10]:
                lines.append(f"- **{component['category']}** — `{component['raw_name'][:80]}`")
            lines.append("")

        if components:
            prices = [l["price_cents"] for c in components for l in c["listings"] if l["price_cents"]]
            if prices:
                lines.append("## Sanity check")
                lines.append("")
                lines.append(f"- Component listings with a price: {len(prices)}")
                lines.append(f"- Median price: {statistics.median(prices) / 100:.2f} €")
                lines.append(f"- Min {min(prices) / 100:.2f} € / max {max(prices) / 100:.2f} €")
                lines.append("")

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "normalisation_report.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path


class SpecificationReportWriter:
    """Render specification coverage using the field map supplied by a worker."""

    def __init__(self, field_map):
        self.field_map = field_map

    def write(self, out_dir: Path, store: Dict[str, Any]) -> Path:
        items = store["items"]
        by_field: Dict[str, Dict[str, int]] = {}
        unmapped_counts: Dict[str, int] = {}
        per_category_total: Dict[str, int] = {}
        per_category_ok: Dict[str, int] = {}
        failures: List[Tuple[str, str, str]] = []

        for url, entry in items.items():
            category = entry.get("category", "?")
            per_category_total[category] = per_category_total.get(category, 0) + 1
            if entry.get("status") == "ok":
                per_category_ok[category] = per_category_ok.get(category, 0) + 1
            else:
                failures.append((category, entry.get("name", "")[:60], entry.get("error", "?")))
            counts = by_field.setdefault(category, {})
            for field, value in (entry.get("specs") or {}).items():
                if value not in (None, [], ""):
                    counts[field] = counts.get(field, 0) + 1
            for label in entry.get("unmapped", []):
                key = f"{category}: {label}"
                unmapped_counts[key] = unmapped_counts.get(key, 0) + 1

        lines: List[str] = []
        lines.append(f"# Product-page data sheet report — {date.today().isoformat()}")
        lines.append("")
        lines.append(f"Fetched **{len(items)}** product pages; **{sum(per_category_ok.values())}** "
                     f"parsed successfully, {len(failures)} failed.")
        lines.append("")
        lines.append("Values here are **parsed from the shop's own data sheet**, not inferred from the "
                     "product name. Unmapped labels are listed below instead of being guessed.")
        lines.append("")

        lines.append("## Coverage per category and field")
        lines.append("")
        lines.append("| Category | Products | Field | Parsed | Coverage |")
        lines.append("|---|---|---|---|---|")
        for category in CATEGORIES:
            total = per_category_total.get(category)
            if not total:
                continue
            for field in self.field_map.get(category, {}):
                found = by_field.get(category, {}).get(field, 0)
                pct = round(100 * found / total)
                status = "✅" if pct >= 80 else ("⚠️" if pct >= 40 else "❌")
                lines.append(f"| {category} | {total} | `{field}` | {found} | {status} {pct}% |")
        lines.append("")

        if unmapped_counts:
            lines.append("## Labels we could not map (top 25)")
            lines.append("")
            lines.append("These are preserved for review — add them to the selected retailer specification field map "
                         "when they matter for a compatibility rule.")
            lines.append("")
            for key, count in sorted(unmapped_counts.items(), key=lambda kv: -kv[1])[:25]:
                lines.append(f"- {count:>4}× {key}")
            lines.append("")

        if failures:
            lines.append("## Failed pages")
            lines.append("")
            for category, name, error in failures[:20]:
                lines.append(f"- **{category}** `{name}` — {error}")
            lines.append("")

        retained = [(url, entry['last_attempt']) for url, entry in items.items()
                    if entry.get('status') == 'ok' and entry.get('last_attempt', {}).get('status') in {'failed', 'empty'}]
        if retained:
            lines.extend(['## Failed refresh attempts (earlier specs retained)', ''])
            for url, attempt in retained:
                lines.append(f"- {url} — {attempt.get('error', attempt['status'])}")
            lines.append('')

        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "specs_report.md"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path
