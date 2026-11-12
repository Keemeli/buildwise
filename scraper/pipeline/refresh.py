"""Plan retailer stages, execute subprocesses and record refresh results."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from scraper.config import PROJECT_ROOT, CATEGORIES

SCRAPER_DIR = PROJECT_ROOT / "scraper"
LOG_PATH = PROJECT_ROOT / "data" / "refresh_log.jsonl"
TAIL_LINES = 6


def run_stage(name: str, args: list[str]) -> dict:
    """Run one stage, streaming its output. Returns a record for the log."""
    cmd = [sys.executable, "-m", "scraper", *args]
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


class RefreshPipeline:
    """Plan retailer stages and run the shared catalogue pipeline in order.

    A stage runner can be injected for offline planning tests. Existing callers
    can continue using the module-level run_stage function.
    """

    def __init__(self, options: argparse.Namespace, categories: list[str], shops: list[str],
                 stage_runner=None, project_root: Path | None = None, log_path: Path | None = None):
        self.options, self.categories, self.shops = options, categories, shops
        self.stage_runner = run_stage if stage_runner is None else stage_runner
        self.project_root = PROJECT_ROOT if project_root is None else project_root
        self.data_dir = getattr(options, "data_dir", self.project_root / "data")
        self.web_output = getattr(options, "web_output", self.project_root / "web/data/components.json")
        self.log_path = (self.data_dir / "refresh_log.jsonl") if log_path is None else log_path

    def build_stages(self) -> list[tuple[str, list[str]]]:
        stages: list[tuple[str, list[str]]] = []
        common = ["--pages", str(self.options.pages), "--delay", str(self.options.delay),
                  "--data-dir", str(self.data_dir)]
        if not self.options.skip_scrape:
            if "datatronic" in self.shops:
                for category in self.categories:
                    stages.append((f"datatronic-{category}", ["collect", "--shop", "datatronic",
                                   "--category", category, *common]))
            if "jimms" in self.shops:
                collection = ["collect", "--shop", "jimms", *common]
                if self.options.jimms_category_url and self.options.jimms_input:
                    raise ValueError("use --jimms-input or --jimms-category-url, not both")
                if self.options.jimms_input:
                    collection += ["--input", str(self.options.jimms_input.resolve())]
                else:
                    if self.options.jimms_category_url:
                        if len(self.categories) != 1:
                            raise ValueError("Jimms URL override needs exactly one --categories value")
                        collection += ["--url", self.options.jimms_category_url]
                    else:
                        from scraper.retailers.jimms import CATEGORY_URLS
                        missing = [c for c in self.categories if c not in CATEGORY_URLS]
                        if missing:
                            raise ValueError("Jimms categories need verified URLs: " + ", ".join(missing)
                                             + "; choose gpu/cpu, supply a single --jimms-category-url or --jimms-input")
                    for category in self.categories:
                        collection += ["--category", category]
                stages.append(("jimms-collect", collection))
        if not self.options.skip_specs and "datatronic" in self.shops:
            specs_args = ["specs", "--shop", "datatronic", "--delay", str(self.options.delay),
                          "--raw-dir", str(self.data_dir / "raw"),
                          "--out", str(self.data_dir / "normalised")]
            for category in self.categories:
                specs_args += ["--category", category]
            if self.options.cold:
                specs_args.append("--force")
            stages.append(("datatronic-specs", specs_args))
        stages.append(("normalise", ["normalise", "--raw-dir", str(self.data_dir / "raw"),
                                    "--out", str(self.data_dir / "normalised")]))
        stages.append(("export", ["export", "--source", str(self.data_dir / "normalised/components.json"),
                                 "--target", str(self.web_output)]))

        return stages

    def run(self) -> int:
        stages = self.build_stages()
        started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        started = time.monotonic()
        records: list[dict] = []
        failed = None

        print(f"BuildWise refresh — {len(stages)} stages "
              f"({', '.join(name for name, _ in stages)})")
        for name, stage_args in stages:
            record = self.stage_runner(name, stage_args)
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
        components_path = self.data_dir / "normalised" / "components.json"
        specs_path = self.data_dir / "normalised" / "specs.json"
        web_path = self.web_output
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
                json.loads(web_path.read_text(encoding="utf-8"))
                == json.loads(components_path.read_text(encoding="utf-8")))

        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
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
        print(f"    log: {self.log_path.relative_to(self.project_root) if self.log_path.is_relative_to(self.project_root) else self.log_path}")
        if summary.get("web_copy_matches_normalised") is False:
            print("    WARNING: the web copy does not match the normalised catalogue", file=sys.stderr)
        return 0 if not failed else 1


