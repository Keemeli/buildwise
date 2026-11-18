# BuildWise

**Finnish-price PC build advisor** — tell it your budget and the game you play, and get a compatible PC build with prices from Finnish retailers and an honest FPS estimate.

> "€1200 for CS2 at 1080p" → 2–3 candidate builds, each with a compatibility check, total price, and an estimated performance range.

Course project for **Product Design and Implementation (15 cr), OAMK autumn 2026**.
Demo video + self-assessment deadline: **15.12.2026**.

**Live demo:** https://buildwise-two-rust.vercel.app/ — deployed from `main` (root directory `web`, Next.js preset). Every pull request gets its own preview deployment, linked automatically from the PR.

---

## What it does

1. The user enters a budget, the game(s) they play, a resolution (1080p / 1440p / 4K) and optional preferences (quiet, small, upgrade path).
2. The app parses the request, filters the component catalogue, runs the **compatibility engine**, scores candidate builds and returns **2–3 builds** with trade-off explanations.
3. Each build shows the total price (Finnish retailers), per-part prices, compatibility status, an estimated FPS range per selected game, and a price history chart.

## Project status

Sprint 1 (week of 28.10–5.11) — what is actually in `main` today:

| Deliverable | State |
|---|---|
| Repository, branch protection, Kanban board as GitHub issues | Done — every change went through a pull request (4 merged, each reviewed by a team member) |
| Database schema (`shops`, `components`, `listings`, `price_snapshots`, `scrape_runs` + `latest_prices` view) | Done — prices as integer cents, one snapshot per listing per day |
| Datatronic scraper | Done — **336 products** from 7 categories, each with a price and a product URL; raw HTML cached, every run logged |
| Component normaliser | Done — 336 raw rows → **332 components**, plus a coverage report that lists what could **not** be parsed instead of guessing it |
| Web application | Deployed on the real catalogue, with a grey **"could not check"** state wherever the data cannot answer a compatibility question |
| Proshop / Jimms scrapers (Andrew) | In progress |
| CI workflow | Not started |
| Recommendation engine, FPS estimates from measured data | Not started — FPS numbers are still mock data |

Board: **[BuildWise — Sprint board](https://github.com/Keemeli/buildwise/projects)**

## Team

| Name | GitHub | Role |
|---|---|---|
| Eemeli Karjalainen | [@Keemeli](https://github.com/Keemeli) | Data pipeline, scraping, database |
| Joonas Heiskari | [@JoonasHeisk](https://github.com/JoonasHeisk) | Web application, deployment, CI |
| Andrew | [@andrew11oamk](https://github.com/andrew11oamk) | Scraping (Proshop/Jimms), component normalisation |

Supervisors: Teemu Korpela ([@t2946282](https://github.com/t2946282)), Pekka Alaluukas ([@alaluuk](https://github.com/alaluuk)).

## Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Next.js 16 + React 19 + Recharts | Live at https://buildwise-two-rust.vercel.app/ (Vercel Hobby; project root `web`) |
| API / engine | Node (Express) | Compatibility rules, scoring, intent parsing |
| Data worker | Python (httpx + BeautifulSoup) | Nightly cron, runs independently |
| Database | PostgreSQL (Supabase free tier) | Falls back to SQLite locally |
| CI | GitHub Actions | Tests run on every pull request |

## Architecture

```
            ┌─────────────────────────────┐
            │  Finnish retailers          │
            │  Datatronic · Jimms · Proshop│
            └──────────────┬──────────────┘
                           │ nightly scrape (rate-limited, cached)
                           ▼
                 ┌───────────────────┐
                 │  Python worker    │
                 │  parse + normalise│
                 └─────────┬─────────┘
                           ▼
                 ┌───────────────────┐        ┌────────────────────┐
                 │  PostgreSQL       │◄──────►│  Engine            │
                 │  components       │        │  compatibility     │
                 │  shops            │        │  scoring           │
                 │  price_snapshots  │        │  performance model │
                 └─────────┬─────────┘        └─────────┬──────────┘
                           │                            │
                           └──────────► API ────────────┘
                                         │
                                         ▼
                                  Next.js web app
```

## Data sources

| Source | Method | Notes |
|---|---|---|
| Datatronic.fi | Category listing pages (`js-product-list` container) | 24 products per page; GPU category has 480 products, 20 pages |
| Jimms.fi | Product pages expose `meta[property="product:price:amount"]` | One request per product, throttled |
| Proshop.fi | Category pages contain prices in HTML | ~50 products per request |
| Verkkokauppa.com | Not used | JS-rendered tiles, scraper-hostile robots.txt |
| Performance estimates | Published benchmark data, transcribed | Tiered confidence, see below |

**Scraping rules we hold ourselves to:** respect `robots.txt`, one request at a time with a delay, identify the crawler with a contact User-Agent, cache raw HTML and store daily price snapshots, always show the retailer and the timestamp of the price, never republish a retailer catalogue as our own.

**Pipeline:** `python3 -m scraper collect` (raw JSON + cached HTML) → `python3 -m scraper normalise` → `data/normalised/components.json` and `data/normalised/normalisation_report.md`. The report records coverage per spec field and lists every row that could not be parsed, so gaps are visible instead of hidden. A value that is *inferred* rather than read from the product name carries a source marker (`socket_source: inferred_from_sku`, `memory_type_source: inferred_from_chipset`) so the engine can weight it as lower confidence. Rows that are not hardware at all (assembly services, monitor accessories listed inside a component category) are excluded into `excluded_non_components.json`.

**Performance model:** estimated FPS = GPU index × per-game resolution scaling × ray-tracing multiplier × frame-generation uplift (capability-gated) ÷ CPU-bound penalty, with VRAM limits. Coverage is explicitly tiered:

- **Tier A (~30 games):** calibrated from published benchmarks → shown as "estimate"
- **Tier B (~150 games):** modelled from genre defaults → shown as "rough estimate ±20%"
- **Tier C:** "not enough data" — we never invent a number

## Repository layout

```
buildwise/
├── scraper/          # Python data worker: fetch, parse, normalise
├── data/
│   ├── raw/          # raw scraped payloads (JSON, cached HTML)
│   ├── normalised/   # components.json + normalisation report
│   └── schema.sql    # database schema
├── web/              # Next.js application (compatibility rules in web/lib/compat.js)
├── docs/             # written-down rules and design decisions
└── .github/workflows # CI
```

The build checker's rules are written down in
[`docs/compatibility-rules.md`](docs/compatibility-rules.md): every check it makes, which
field it reads for that check, what it refuses to decide, and what has to be added when a
new rule appears.

## Getting started (development)

```bash
# data worker (run from the repository root)
# Python 3.11+ is required: protego>=0.7 needs 3.10+, and 3.9 crashes the CLI on the
# PEP 604 unions in scraper/common (TypeError: unsupported operand type(s) for |).
python3.11 -m venv scraper/.venv && source scraper/.venv/bin/activate
pip install -r scraper/requirements.txt
RETAILER=jimms  # or datatronic
python3 -m scraper collect --shop "$RETAILER" --category gpu --pages 2
python3 -m scraper specs --shop "$RETAILER" --category gpu --limit 25
```

See [the scraper guide](scraper/README.md#common-usage) for shared commands,
supported capabilities and optional retailer inputs.

Output lands in `data/raw/` (one JSON per category/page), with raw HTML cached in
`data/raw/html/` and one line per run in `data/raw/scrape_runs.jsonl`.

**Refreshing everything (the normal way):** the pipeline is four stages and the web
app reads a copy of the last one, so there is one command instead of four:

```bash
python3 -m scraper refresh --pages 1
python3 -m scraper refresh --shops jimms,datatronic --categories gpu --pages 2
python3 -m scraper refresh --offline       # no network: normalise + export
python3 -m scraper refresh --skip-specs    # collect prices, normalise + export
python3 -m scraper refresh --cold          # force specs for selected retailers
```

Every stage must succeed, the run is appended to `data/refresh_log.jsonl`, and the
command prints what it actually produced (components, how many have product-page
specs, whether the web copy matches the catalogue).

`python3 -m scraper export --check` answers one question on its own: does the copy
the deployed site reads still match the normalised catalogue?

```bash
# web app
cd web
npm install
npm run dev
```

## Roadmap

| Milestone | Date | Deliverable |
|---|---|---|
| Repo + first data proof | 5.11 | ✅ 336 products scraped, board active, web deployed |
| Normalisation + compatibility rules v1 | 17.11 | parts normalised, socket/RAM/PSU rules tested |
| Budget recommendation works | 24.11 | "€1200 CS2 1080p" returns 3 builds |
| Performance estimates + charts | 1.12 | FPS ranges with confidence labels |
| Feature freeze | 8.12 | polish, tests, docs |
| Submission | 15.12 | 5-min video + PDF + self-assessment |

## How we work

- Every change goes through a branch and a pull request, approved by at least one team member
- Daily commits, daily board updates, near-daily progress posts in the course Discord
- Hours log in `docs/hours.md`
- Weekly team meeting

## License

MIT — see [LICENSE](LICENSE).