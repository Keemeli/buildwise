# Normalisation report — 2026-11-03

Scanned 336 raw products from `data/raw/`, produced **332 unique components** (2 duplicate rows merged).

Missing values are reported, not filled. A `null` spec means the shop's product name does not contain that information.

## Coverage per category

| Category | Components | Field | Parsed | Coverage |
|---|---|---|---|---|
| gpu | 47 | `chipset` | 45 | 96% |
| gpu | 47 | `vram_gb` | 44 | 94% |
| gpu | 47 | `memory_type` | 47 | 100% |
| gpu | 47 | `gpu_vendor` | 47 | 100% |
| cpu | 47 | `family` | 46 | 98% |
| cpu | 47 | `socket` | 45 | 96% |
| cpu | 47 | `base_clock_ghz` | 32 | 68% |
| cpu | 47 | `cache_mb` | 46 | 98% |
| motherboard | 48 | `chipset` | 48 | 100% |
| motherboard | 48 | `socket` | 48 | 100% |
| motherboard | 48 | `form_factor` | 43 | 90% |
| motherboard | 48 | `memory_type` | 47 | 98% |
| memory | 48 | `memory_type` | 48 | 100% |
| memory | 48 | `capacity_gb` | 48 | 100% |
| memory | 48 | `modules` | 48 | 100% |
| memory | 48 | `speed_mhz` | 42 | 88% |
| memory | 48 | `cas_latency` | 21 | 44% |
| storage | 48 | `capacity_gb` | 48 | 100% |
| storage | 48 | `interface` | 46 | 96% |
| storage | 48 | `form_factor` | 46 | 96% |
| storage | 48 | `pcie_gen` | 21 | 44% |
| psu | 48 | `wattage_w` | 48 | 100% |
| psu | 48 | `efficiency` | 11 | 23% |
| psu | 48 | `atx_version` | 8 | 17% |
| psu | 48 | `form_factor` | 47 | 98% |
| case | 46 | `form_factor` | 33 | 72% |
| case | 46 | `color` | 46 | 100% |

## Products needing review (fewest specs found)

- **psu** — `Thermalright SG 1000W` — missing: efficiency, atx_version, form_factor
- **storage** — `Samsung 2TB 9100 PRO` — missing: interface, form_factor, pcie_gen
- **psu** — `be quiet! Pure Power 13 M | 850W virtalähdeyksikkö 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **psu** — `be quiet! Pure Power 13 M | 1000W virtalähdeyksikkö 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **psu** — `be quiet! PURE POWER 12 850W virtalähdeyksikkö 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **psu** — `be quiet! PURE POWER 12 650W virtalähdeyksikkö 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **psu** — `be quiet! PURE POWER 12 550W virtalähdeyksikkö 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **psu** — `be quiet! POWER ZONE 2 1000W virtalähdeyksikkö 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **memory** — `Team Group DELTA RGB muistimoduuli 32 GB 2 x 16 GB DDR5 288-pin DIMM` — missing: speed_mhz, cas_latency
- **psu** — `Seasonic Nicht kategorisiert virtalähdeyksikkö 650 W ATX musta` — missing: efficiency, atx_version
- **psu** — `Seasonic Focus GX virtalähdeyksikkö 850 W 20+4 pin ATX ATX musta` — missing: efficiency, atx_version
- **psu** — `Seasonic Focus GX virtalähdeyksikkö 750 W 24-pin ATX ATX Valkoinen` — missing: efficiency, atx_version
- **psu** — `Seasonic FOCUS SGX-750 (2021) virtalähdeyksikkö 750 W 20+4 pin ATX SFX Musta` — missing: efficiency, atx_version
- **psu** — `Seasonic CORE GX-750-V2 virtalähdeyksikkö 750 W ATX musta` — missing: efficiency, atx_version
- **psu** — `Seasonic CORE BC-650 virtalähdeyksikkö 650 W 20+4 pin ATX ATX musta` — missing: efficiency, atx_version

## Rows excluded as non-components

2 scraped rows were not hardware (assembly services or accessories the shop lists inside a component category). They are kept in `excluded_non_components.json` but must never reach the compatibility engine.

- `AMD Ryzen 7 7800X3D suoritin 4,2 GHz 96 MB L3 TRAY Kasauspalveluun`
- `BenQ ScreenBar Halo 2 Näytön valo Harmaa`

## Sanity check

- Component listings with a price: 334
- Median price: 173.90 €
- Min 24.90 € / max 13349.00 €

