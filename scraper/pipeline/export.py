"""Catalogue export and complete-content drift checking."""
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


def load(path: Path) -> dict:
    if not path.exists():
        print(f"missing {path} — run: python3 -m scraper normalise", file=sys.stderr)
        raise SystemExit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def summarise(payload: dict) -> str:
    components = payload.get("components", [])
    parsed = sum(1 for c in components if c.get("spec_sources"))
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

        if check:
            if not self.target.exists():
                print(f"web copy missing: {self.target}", file=sys.stderr)
                return 1
            target = load(self.target)
            print("target  web/data/components.json")
            print(summarise(target))
            stale = source != target
            print("\nweb copy is STALE — run without --check to refresh" if stale
                  else "\nweb copy is up to date")
            return 1 if stale else 0

        self.target.parent.mkdir(parents=True, exist_ok=True)
        self.target.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
        display = self.target.relative_to(self.project_root) if self.target.is_relative_to(self.project_root) else self.target
        print(f"\nwrote {display}")
        print("commit it — Vercel deploys from the repository, so an uncommitted copy "
              "does not reach the deployed site")
        return 0


