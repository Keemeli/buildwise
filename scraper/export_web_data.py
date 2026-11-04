#!/usr/bin/env python3
"""BuildWise — export the normalised catalogue for the web app.

The web app reads `web/data/components.json`, which is a *copy* of
`data/normalised/components.json`. Copies drift: the deployed site kept showing
name-only specs for two days after the product-page data sheet work landed, so the
wattage estimate had no numbers to add up. This script is the one supported way to
refresh that copy, and `--check` reports drift without writing anything.

Why a copy at all: the web app is deployed on Vercel, which only sees the
repository. The Python pipeline runs on our own machine, so the pipeline output is
committed for the deployment to read.

Usage:
    python export_web_data.py            # refresh web/data/components.json
    python export_web_data.py --check    # report drift, change nothing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE = PROJECT_ROOT / "data" / "normalised" / "components.json"
TARGET = PROJECT_ROOT / "web" / "data" / "components.json"

# Fields the web app shows as "we could not check" when they are missing.
KEY_FIELDS = ("power_w", "recommended_psu_w", "length_mm", "tdp_w", "socket",
              "wattage_w", "max_gpu_length_mm", "memory_type")


def load(path: Path) -> dict:
    if not path.exists():
        print(f"missing {path} — run: python scraper/normalise.py", file=sys.stderr)
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the catalogue for the web app.")
    parser.add_argument("--check", action="store_true",
                        help="report whether the web copy is stale, write nothing")
    args = parser.parse_args()

    source = load(SOURCE)
    print("source  data/normalised/components.json")
    print(summarise(source))

    if args.check:
        if not TARGET.exists():
            print(f"web copy missing: {TARGET}", file=sys.stderr)
            return 1
        target = load(TARGET)
        print("target  web/data/components.json")
        print(summarise(target))
        stale = (source.get("generated_at") != target.get("generated_at")
                 or source.get("component_count") != target.get("component_count")
                 or sum(1 for c in target.get("components", []) if c.get("spec_sources"))
                 != sum(1 for c in source.get("components", []) if c.get("spec_sources")))
        print("\nweb copy is STALE — run without --check to refresh" if stale
              else "\nweb copy is up to date")
        return 1 if stale else 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(json.dumps(source, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {TARGET.relative_to(PROJECT_ROOT)}")
    print("commit it — Vercel deploys from the repository, so an uncommitted copy "
          "does not reach the deployed site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
