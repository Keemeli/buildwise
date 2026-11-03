-- BuildWise database schema
-- Target: PostgreSQL (Supabase free tier). Local dev may use SQLite — see notes at the bottom.
--
-- Design rules:
--   1. Money is stored as INTEGER cents (price_cents). Never floats.
--   2. One price row per component, per shop, per day (UNIQUE constraint).
--   3. Category-specific specs live in a JSONB column for now; they are promoted
--      to real columns once the compatibility rules stabilise (sprint 3).

CREATE TABLE shops (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,          -- 'Datatronic', 'Jimms', 'Proshop'
    domain        TEXT NOT NULL,                 -- 'datatronic.fi'
    base_url      TEXT NOT NULL,
    scraping_note TEXT,                          -- robots.txt / etiquette notes
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE components (
    id            SERIAL PRIMARY KEY,
    category      TEXT NOT NULL
                  CHECK (category IN ('cpu','motherboard','memory','gpu','storage','psu','case','other')),
    brand         TEXT,
    model         TEXT NOT NULL,
    specs         JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- specs keys by category (examples):
    --   cpu:         socket, cores, threads, tdp_w, igpu
    --   motherboard: socket, chipset, memory_type, form_factor, m2_slots
    --   memory:      memory_type, capacity_gb, speed_mhz, modules
    --   gpu:         vram_gb, tdp_w, length_mm, rt_support, fg_support
    --   storage:     capacity_gb, interface, form_factor
    --   psu:         wattage_w, efficiency, modular, length_mm
    --   case:        form_factors, max_gpu_length_mm, max_cooler_height_mm
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (category, brand, model)
);

CREATE TABLE listings (
    id             SERIAL PRIMARY KEY,
    component_id   INTEGER NOT NULL REFERENCES components(id) ON DELETE CASCADE,
    shop_id        INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE,
    external_id    TEXT,                         -- shop's own product id, e.g. '118634'
    url            TEXT NOT NULL,
    first_seen_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (component_id, shop_id)
);

CREATE TABLE price_snapshots (
    id             BIGSERIAL PRIMARY KEY,
    listing_id     INTEGER NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    price_cents    INTEGER NOT NULL CHECK (price_cents >= 0),
    currency       CHAR(3) NOT NULL DEFAULT 'EUR',
    in_stock       BOOLEAN,
    snapshot_date  DATE NOT NULL,
    scraped_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (listing_id, snapshot_date)
);

CREATE TABLE scrape_runs (
    id             SERIAL PRIMARY KEY,
    shop_id        INTEGER NOT NULL REFERENCES shops(id),
    category       TEXT NOT NULL,
    pages_fetched  INTEGER NOT NULL,
    items_found    INTEGER NOT NULL,
    started_at     TIMESTAMPTZ NOT NULL,
    finished_at    TIMESTAMPTZ,
    status         TEXT NOT NULL CHECK (status IN ('running','ok','partial','failed')),
    note           TEXT
);

CREATE INDEX idx_components_category      ON components (category);
CREATE INDEX idx_components_specs         ON components USING GIN (specs);
CREATE INDEX idx_snapshots_listing_date   ON price_snapshots (listing_id, snapshot_date DESC);
CREATE INDEX idx_snapshots_date           ON price_snapshots (snapshot_date DESC);
CREATE INDEX idx_listings_component       ON listings (component_id);

-- Handy view: latest price per listing
CREATE VIEW latest_prices AS
SELECT l.id AS listing_id, c.category, c.brand, c.model, s.name AS shop,
       p.price_cents, p.currency, p.snapshot_date
FROM price_snapshots p
JOIN listings  l ON l.id = p.listing_id
JOIN components c ON c.id = l.component_id
JOIN shops      s ON s.id = l.shop_id
WHERE p.snapshot_date = (SELECT max(snapshot_date) FROM price_snapshots p2
                         WHERE p2.listing_id = p.listing_id);

-- ---------------------------------------------------------------------------
-- SQLite notes for local development:
--   * replace SERIAL with INTEGER PRIMARY KEY AUTOINCREMENT
--   * replace JSONB with TEXT (store JSON as text)
--   * replace TIMESTAMPTZ with TEXT (ISO-8601 strings)
--   * drop "USING GIN (specs)"; use a plain index on category instead
-- ---------------------------------------------------------------------------