"""Benchmark data for the FPS estimate, read from CheckFPS's public pages.

Why the labels are what they are
--------------------------------
CheckFPS says in its own FAQ that its numbers are *"estimates designed to reflect real-world
relative performance, not lab measurements"*. Every row this tool writes therefore carries
`measured: false`, the URL it came from and the date it was read. The builder shows that
label, and nothing in this pipeline claims to be a measurement of the hardware.

Its `robots.txt` allows the public pages and disallows `/api/`; this tool reads public pages
only, through the same rate-limited, robots-checked fetcher the shop crawler uses, and never
touches the API. The figures belong to CheckFPS: attribution stays in the artefact and in
the UI, and asking them for permission is the clean next step before any public use.

Two page shapes are read
------------------------
`/en/fps-calculator/<game>/<gpu>` — a quality × resolution grid, each cell an average and a
1% low ("135 FPS min 117"), plus the game's stated RAM need and the reference CPU the figures
assume. These are the **anchors** our model scales.

`/en/gpu/<gpu>/benchmark` — one card's FPS per game at 1080p/1440p/4K, its specs, and its
**CPU ceilings** (per processor, per resolution). One page per card gives the relative index
for every other card in our catalogue and the ceiling that keeps a CPU-bound estimate honest.

Run:  scraper/.venv/bin/python -m scraper.benchmarks.checkfps
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_ROOT = PROJECT_ROOT / "data/raw/html"
OUT_DIR = PROJECT_ROOT / "data/benchmarks"

SOURCE_NAME = "CheckFPS (checkfps.io)"
SOURCE_NOTE = (
    "CheckFPS states its figures are estimates from its own engine, not lab measurements; "
    "read from public pages, robots.txt respected (/api/ not used)."
)

# Our game id -> the slug CheckFPS uses. Only the games the builder offers.
GAMES = {
    "cs2": "counter-strike-2",
    "fortnite": "fortnite",
    "valorant": "valorant",
    "cyberpunk2077": "cyberpunk-2077",
    "minecraft": "minecraft",
}
GAME_NAMES = {
    "cs2": "Counter-Strike 2", "fortnite": "Fortnite", "valorant": "Valorant",
    "cyberpunk2077": "Cyberpunk 2077", "minecraft": "Minecraft",
}
RESOLUTIONS = ("1080p", "1440p", "4K")
PRESETS = ("ultra", "high", "medium", "low")

# The card the anchors are read for and the index is normalised against. It is the same
# reference our placeholder model already used (RTX 5060 Ti = 1.0), so nothing shifts.
ANCHOR_SLUG = "rtx-5060-ti"
ANCHOR_LABEL = "RTX 5060 Ti"

# GPUs the index is built from: the ranked list CheckFPS publishes, read from its tier-list
# page's structured data (order only — the numbers come from each card's own page).
TIER_LIST_URL = "https://checkfps.io/en/gpu"

CELL = re.compile(r"(\d{2,4})\s*FPS.*?min\s*(\d{1,4})", re.I)
RAM_NEED = re.compile(r"\bRAM\s*(\d{1,3})\s*GB", re.I)
CPU_NAME = re.compile(r"(?:Intel Core i[3579]-\d{3,5}[A-Z]*|AMD Ryzen [3579] \d{3,4}[A-Z0-9]*)")
# The calculator's own selectors carry the values its figures assume. The first processor
# named in the page text is the *minimum requirement*, a much weaker chip — labelling our
# numbers with that would be wrong by a wide margin.
CPU_SELECT = re.compile(r'<button[^>]*aria-haspopup="listbox"[^>]*>(.*?)</button>', re.S)
TABLE = re.compile(r"<table.*?</table>", re.S)
ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_HTML = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
NUMBERS = re.compile(r"\b(\d{2,4})\b")


def reference_cpu(html: str) -> str | None:
    """The processor the page's figures assume: the CPU the calculator has selected."""
    for match in CPU_SELECT.finditer(html):
        name = CPU_NAME.search(text_of(match.group(1)))
        if name:
            return name.group(0)
    return None


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


def table_rows(html: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for table in TABLE.findall(html):
        for row in ROW.findall(table):
            cells = [text_of(c) for c in CELL_HTML.findall(row)]
            if cells:
                rows.append(cells)
    return rows


def parse_quality_grid(html: str) -> dict[tuple[str, str], dict]:
    """(resolution, preset) -> {avg, low} from the quality × resolution table."""
    grid: dict[tuple[str, str], dict] = {}
    for cells in table_rows(html):
        head = " ".join(cells).lower()
        if not head.startswith("quality"):
            continue
        columns = [c for c in cells[1:]]
        order = []
        for label in columns:
            for resolution in RESOLUTIONS:
                if label.startswith(resolution):
                    order.append(resolution)
        for row in table_rows(html):
            if not row or not re.fullmatch(r"(ultra|high|medium|low)", row[0].strip(), re.I):
                continue
            preset = row[0].strip().lower()
            for index, cell in enumerate(row[1:]):
                match = CELL.search(cell)
                if not match or index >= len(order):
                    continue
                grid[(order[index], preset)] = {"avg": int(match.group(1)), "low": int(match.group(2))}
    return grid


def parse_game_meta(html: str) -> dict:
    """The game's stated RAM need and the CPU its figures assume."""
    plain = text_of(re.sub(r"<script.*?</script>", " ", html, flags=re.S))
    ram = RAM_NEED.search(plain)
    return {
        "ramNeedGb": int(ram.group(1)) if ram else None,
        "cpuReference": reference_cpu(html),
    }


def parse_benchmark_page(html: str) -> dict:
    """One card: per-game FPS at three resolutions, its specs and its CPU ceilings."""
    games: list[dict] = []
    cpus: list[dict] = []
    specs: dict = {}
    for row in table_rows(html):
        first = row[0].strip()
        if first == "Game" and len(row) >= 4:
            continue
        if first == "Processor (CPU)" and len(row) >= 4:
            continue
        # per-game rows: name, 1080p, 1440p, 4K, rating
        if len(row) >= 4 and all(re.fullmatch(r"\d{2,4}", cell) for cell in row[1:4]):
            entry = {resolution: int(row[1 + i]) for i, resolution in enumerate(RESOLUTIONS)}
            if re.fullmatch(r"(ultra|high|medium|low)", row[1].strip(), re.I):
                continue
            games.append({"game": re.sub(r"View.*$", "", first).strip(), **entry})
        elif first == "VRAM" and row[1].endswith("GB"):
            specs["vram_gb"] = int(re.sub(r"\D", "", row[1]) or 0)
        elif first == "Power Draw (TDP)":
            specs["tdp_w"] = int(re.sub(r"\D", "", row[1]) or 0)
        elif first == "Tier":
            specs["tier"] = row[1]
    # CPU ceilings live in the table whose header starts with "Processor (CPU)".
    for table in TABLE.findall(html):
        rows = [[text_of(c) for c in CELL_HTML.findall(r)] for r in ROW.findall(table)]
        rows = [r for r in rows if r]
        if rows and rows[0][:1] == ["Processor (CPU)"]:
            for row in rows[1:]:
                numbers = [int(n) for n in row[1:4] if re.fullmatch(r"\d{2,4}", n)]
                if len(numbers) == 3:
                    cpus.append({"cpu": row[0], **{res: numbers[i] for i, res in enumerate(RESOLUTIONS)}})
    return {"games": games, "cpus": cpus, "specs": specs}


def ranked_gpus(html: str) -> list[tuple[str, str]]:
    """(label, slug) for every card the tier list links to.

    The page's structured data carries the published order but is split across script
    chunks, so the order is only a hint: what matters here is the set of cards, and each
    card's own page then supplies its official name and its numbers.
    """
    positions: dict[str, int] = {}
    names: dict[str, str] = {}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        if "/gpu/" not in block:
            continue
        for position, name, url in re.findall(
            r'"position":(\d+),"name":"([^"]+)","url":"([^"]+)"', block
        ):
            slug = url.rstrip("/").split("/gpu/")[-1].replace("/benchmark", "")
            positions[slug] = int(position)
            names[slug] = name

    slugs: list[str] = []
    for slug in re.findall(r'href="/en/gpu/([a-z0-9-]+)/benchmark"', html):
        if slug not in slugs:
            slugs.append(slug)

    def label_for(slug: str) -> str:
        if slug in names:
            return names[slug]
        # Fall back to the card's own text: "NVIDIA | RTX 5070 | ..." -> "RTX 5070".
        block = html[html.find(f'href="/en/gpu/{slug}/benchmark"'):][:1400]
        plain = text_of(block)
        match = re.search(r"\b(RTX|RX|Arc|GTX|Radeon|GeForce)\s?[A-Za-z0-9][A-Za-z0-9 \-]{0,14}", plain)
        return match.group(0).strip() if match else slug.replace("-", " ").upper()

    order = {slug: index for index, slug in enumerate(slugs)}
    slugs.sort(key=lambda slug: (positions.get(slug, 10_000), order[slug]))
    return [(label_for(slug), slug) for slug in slugs]


def chipset_key(name: str) -> str:
    """The key our catalogue uses (see web/lib/catalog-shared.js chipsetKey)."""
    return re.sub(r"\s+", "", name.upper())


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    offline = "--offline" in argv
    if str(PROJECT_ROOT / "scraper") not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from scraper.common.fetching import PageFetcher  # imported here so --help stays cheap

    fetcher = PageFetcher(CACHE_ROOT, "checkfps", {"checkfps.io"}, delay=1.2, offline=offline)
    today = date.today().isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def get(url: str) -> str | None:
        try:
            html, _path, origin = fetcher.fetch(url)
            print(f"    {origin:7} {url}")
            return html
        except Exception as exc:                          # noqa: BLE001 - report and continue
            print(f"    failed  {url}: {exc}", file=sys.stderr)
            return None

    # 1. The ranked list, for the order and the set of cards.
    tier_html = get(TIER_LIST_URL)
    ranked = ranked_gpus(tier_html) if tier_html else []
    print(f"  ranked cards: {len(ranked)}")
    if not ranked:
        ranked = [(ANCHOR_LABEL, ANCHOR_SLUG)]

    # 2. Every card's own page: per-game FPS, specs, CPU ceilings.
    benchmarks: dict[str, dict] = {}
    for name, slug in ranked:
        html = get(f"https://checkfps.io/en/gpu/{slug}/benchmark")
        if not html:
            continue
        parsed = parse_benchmark_page(html)
        parsed.update({"name": name, "slug": slug, "source": f"https://checkfps.io/en/gpu/{slug}/benchmark"})
        benchmarks[slug] = parsed

    # 3. Per game × anchor card: the quality grid with averages and 1% lows.
    anchors: dict[str, dict] = {}
    for game, slug in GAMES.items():
        html = get(f"https://checkfps.io/en/fps-calculator/{slug}/{ANCHOR_SLUG}")
        if not html:
            continue
        grid = parse_quality_grid(html)
        meta = parse_game_meta(html)
        anchors[game] = {
            "name": GAME_NAMES.get(game, game),
            "slug": slug,
            "gpu": ANCHOR_LABEL,
            "source": f"https://checkfps.io/en/fps-calculator/{slug}/{ANCHOR_SLUG}",
            "grid": {f"{resolution}|{preset}": cell for (resolution, preset), cell in grid.items()},
            **meta,
        }
        print(f"  {game}: {len(grid)} cells, RAM need {meta['ramNeedGb']}, reference CPU {meta['cpuReference']}")
    fetcher.close()

    (OUT_DIR / "raw-cards.json").write_text(json.dumps({
        "source": {"name": SOURCE_NAME, "note": SOURCE_NOTE, "retrieved": today,
                   "tierList": TIER_LIST_URL, "anchorGpu": ANCHOR_LABEL},
        "cards": benchmarks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT_DIR / "fps-anchors.json").write_text(json.dumps({
        "source": {"name": SOURCE_NAME, "note": SOURCE_NOTE, "retrieved": today,
                   "anchorGpu": ANCHOR_LABEL},
        "measured": False,
        "games": anchors,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. The relative index: each card's FPS per resolution against the anchor card's.
    anchor_card = benchmarks.get(ANCHOR_SLUG) or {}
    index: dict[str, dict[str, float]] = {}
    for slug, card in benchmarks.items():
        if not card.get("games"):
            continue
        row: dict[str, float] = {}
        for resolution in RESOLUTIONS:
            anchor_fps = {}
            for entry in anchor_card.get("games", []):
                if entry.get(resolution):
                    anchor_fps[entry["game"]] = entry[resolution]
            ratios = [
                entry[resolution] / anchor_fps[entry["game"]]
                for entry in card["games"]
                if entry.get(resolution) and anchor_fps.get(entry["game"])
            ]
            if ratios:
                row[resolution] = round(sum(ratios) / len(ratios), 3)
        if row:
            index[chipset_key(card["name"])] = row
    (OUT_DIR / "gpu-index.json").write_text(json.dumps({
        "source": {"name": SOURCE_NAME, "note": SOURCE_NOTE, "retrieved": today},
        "reference": ANCHOR_LABEL,
        "index": dict(sorted(index.items())),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 5. CPU ceilings: the anchor card's per-CPU numbers, kept per CPU and resolution.
    ceilings: dict[str, dict[str, int]] = {}
    for entry in anchor_card.get("cpus", []):
        ceilings[entry["cpu"]] = {resolution: entry[resolution] for resolution in RESOLUTIONS}
    (OUT_DIR / "cpu-ceilings.json").write_text(json.dumps({
        "source": {"name": SOURCE_NAME, "note": SOURCE_NOTE, "retrieved": today,
                   "gpu": ANCHOR_LABEL},
        "ceilings": dict(sorted(ceilings.items())),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # 6. The shape the performance model eats, for the web app to read: one row per game,
    #    resolution and preset, with the average and the measured low ratio, the game's RAM
    #    need, and the CPU ceiling its figures assume. Everything carries its source.
    reference_cpu_name = next((game.get("cpuReference") for game in anchors.values()
                               if game.get("cpuReference")), None)
    reference_ceiling = ceilings.get(reference_cpu_name or "", {})
    cpu_index = {
        cpu: {resolution: round(values[resolution] / reference_ceiling[resolution], 3)
              for resolution in RESOLUTIONS if reference_ceiling.get(resolution)}
        for cpu, values in ceilings.items()
    } if reference_ceiling else {}

    games_out: dict[str, dict] = {}
    for game, payload in anchors.items():
        rows = []
        for cell, values in sorted(payload["grid"].items()):
            resolution, preset = cell.split("|")
            rows.append({
                "resolution": resolution,
                "preset": preset,
                "avg": values["avg"],
                "low": values["low"],
                "lowRatio": round(values["low"] / values["avg"], 3) if values["avg"] else None,
                "cpuCeiling": reference_ceiling.get(resolution),
                "measured": False,
                "source": payload["source"],
                "retrieved": today,
            })
        games_out[game] = {
            "name": payload["name"],
            "rows": rows,
            "ramNeedGb": payload["ramNeedGb"],
            "cpuReference": payload["cpuReference"],
            "gpuReference": payload["gpu"],
            "source": payload["source"],
        }
    web_dir = PROJECT_ROOT / "web" / "data"
    web_dir.mkdir(parents=True, exist_ok=True)
    (web_dir / "benchmarks.json").write_text(json.dumps({
        "generated_at": today,
        "source": {"name": SOURCE_NAME, "note": SOURCE_NOTE, "retrieved": today},
        "reference": {"gpu": ANCHOR_LABEL, "cpu": reference_cpu_name},
        "defaultRamGb": 32,
        "cpuIndex": cpu_index,
        "gpuIndex": {"reference": ANCHOR_LABEL, "index": dict(sorted(index.items()))},
        "games": games_out,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"  cards parsed: {len(benchmarks)} | index entries: {len(index)} | "
          f"cpu ceilings: {len(ceilings)} | games: {len(anchors)} | web table: web/data/benchmarks.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
