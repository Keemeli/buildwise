#!/usr/bin/env python3
"""BuildWise — one command to refresh everything the project serves.

Runs the pipeline stages in order and writes a run record, so nobody has to
remember the order or the last forgotten step (the deployed site once served
two-day-old specs exactly that way).

    scrape.py          category listings -> prices (data/raw/*.json)
    specs.py           product pages      -> data/normalised/specs.json
    normalise.py       merges both        -> components.json + reports
    export_web_data.py the copy the deployed web app reads (web/data/)

Usage:
    python refresh.py                  # full refresh (listings + specs from today's cache)
    python refresh.py --pages 1        # only the first listing page per category
    python refresh.py --skip-scrape    # no network at all: re-normalise + re-export what we have
    python refresh.py --skip-specs     # prices only: skip the product-page pass
    python refresh.py --cold           # also refetch product pages (ignores today's cache)
    python refresh.py --categories gpu,cpu

Every stage must succeed; the exit code is non-zero if any stage fails, and the
reason is in the last lines of that stage's output. The run record is appended to
data/refresh_log.jsonl so the project can show a real history instead of a claim.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRAPER_DIR = PROJECT_ROOT / "scraper"
LOG_PATH = PROJECT_ROOT / "data" / "refresh_log.jsonl"
TAIL_LINES = 6

CATEGORIES = ("gpu", "cpu", "motherboard", "memory", "storage", "psu", "case")


def run_stage(name: str, args: list[str]) -> dict:
    """Run one stage, streaming its output. Returns a record for the log."""
    cmd = [sys.executable, str(SCRAPER_DIR / args[0]), *args[1:]]
    print(f"\n=== {name}: {' '.join(args)}", flush=True)
    started = time.monotonic()
    tail: deque[str] = deque(maxlen=TAIL_LINES)

    process = subprocess.Popen(cmd, cwd=PROJECT_ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip("\n")
        print(f"    {line}", flush=True)
        tail.append(line)
    process.wait()
    duration = round(time.monotonic() - started, 1)
    ok = process.returncode == 0
    print(f"  {name}: {'OK' if ok else 'FAILED'} in {duration}s", flush=True)
    return {"stage": name, "args": args, "returncode": process.returncode,
            "duration_s": duration, "ok": ok, "last_lines": list(tail)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh every stage of the BuildWise data pipeline.")
    parser.add_argument("--pages", type=int, default=2, help="listing pages per category")
    parser.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    parser.add_argument("--categories", help="comma-separated subset, e.g. gpu,cpu")
    parser.add_argument("--skip-scrape", action="store_true", help="do not touch the network for listings")
    parser.add_argument("--skip-specs", action="store_true", help="skip the product-page pass")
    parser.add_argument("--cold", action="store_true", help="refetch product pages instead of using today's cache")
    args = parser.parse_args()

    categories = [c.strip() for c in args.categories.split(",")] if args.categories else list(CATEGORIES)
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        parser.error(f"unknown categories: {', '.join(unknown)}")

    stages: list[tuple[str, list[str]]] = []
    if not args.skip_scrape:
        stages.append(("scrape", ["scrape.py", "--pages", str(args.pages), "--delay", str(args.delay)] +
                       (["--category", categories[0]] if len(categories) == 1 else ["--all"])))
    if not args.skip_specs:
        specs_args = ["specs.py", "--delay", str(args.delay)]
        for category in categories:
            specs_args += ["--category", category]
        if args.cold:
            specs_args.append("--force")
        stages.append(("specs", specs_args))
    stages.append(("normalise", ["normalise.py"]))
    stages.append(("export", ["export_web_data.py"]))

    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    started = time.monotonic()
    records: list[dict] = []
    failed = None

    print(f"BuildWise refresh — {len(stages)} stages "
          f"({', '.join(name for name, _ in stages)})")
    for name, stage_args in stages:
        record = run_stage(name, stage_args)
        records.append(record)
        if not record["ok"]:
            failed = name
            print(f"\nstage '{name}' failed — stopping. Its last lines:\n  "
                  + "\n  ".join(record["last_lines"]), file=sys.stderr)
            break

    total = round(time.monotonic() - started, 1)
    status = "ok" if not failed else f"failed at {failed}"

    # What the run actually produced, read back from disk rather than assumed.
    summary: dict[str, object] = {}
    components_path = PROJECT_ROOT / "data" / "normalised" / "components.json"
    specs_path = PROJECT_ROOT / "data" / "normalised" / "specs.json"
    web_path = PROJECT_ROOT / "web" / "data" / "components.json"
    if components_path.exists():
        payload = json.loads(components_path.read_text(encoding="utf-8"))
        summary["components"] = payload.get("component_count")
        summary["components_generated_at"] = payload.get("generated_at")
        summary["components_with_parsed_specs"] = sum(
            1 for c in payload.get("components", []) if c.get("spec_sources"))
    if specs_path.exists():
        specs = json.loads(specs_path.read_text(encoding="utf-8"))
        summary["products_with_page_specs"] = specs.get("item_count")
    if web_path.exists() and components_path.exists():
        summary["web_copy_matches_normalised"] = (
            json.loads(web_path.read_text(encoding="utf-8")).get("generated_at")
            == json.loads(components_path.read_text(encoding="utf-8")).get("generated_at"))

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "duration_s": total,
            "status": status,
            "stages": records,
            "summary": summary,
        }, ensure_ascii=False) + "\n")

    print(f"\n=== refresh {status} in {total}s")
    for key, value in summary.items():
        print(f"    {key}: {value}")
    print(f"    log: {LOG_PATH.relative_to(PROJECT_ROOT)}")
    if summary.get("web_copy_matches_normalised") is False:
        print("    WARNING: the web copy does not match the normalised catalogue", file=sys.stderr)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
