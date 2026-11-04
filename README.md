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

**Pipeline:** `scraper/scrape.py` (raw JSON + cached HTML) → `scraper/normalise.py` → `data/normalised/components.json` and `data/normalised/normalisation_report.md`. The report records coverage per spec field and lists every row that could not be parsed, so gaps are visible instead of hidden. A value that is *inferred* rather than read from the product name carries a source marker (`socket_source: inferred_from_sku`, `memory_type_source: inferred_from_chipset`) so the engine can weight it as lower confidence. Rows that are not hardware at all (assembly services, monitor accessories listed inside a component category) are excluded into `excluded_non_components.json`.

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
├── engine/           # compatibility rules, scoring, performance model
├── web/              # Next.js application
├── docs/             # hours log, meeting notes, design decisions
└── .github/workflows # CI
```

## Getting started (development)

```bash
# data worker
cd scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scrape.py --category gpu --pages 2
python scrape.py --all --pages 2          # every category
```

Output lands in `data/raw/` (one JSON per category/page), with raw HTML cached in
`data/raw/html/` and one line per run in `data/raw/scrape_runs.jsonl`.

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