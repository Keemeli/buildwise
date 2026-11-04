# Normalisation report — 2026-11-05

Scanned 336 raw products from `data/raw/`, produced **332 unique components** (2 duplicate rows merged).

Missing values are reported, not filled. A `null` spec means the shop's product name does not contain that information.

## Coverage per category

| Category | Components | Field | Parsed | Coverage |
|---|---|---|---|---|
| gpu | 47 | `chipset` | 45 | 96% |
| gpu | 47 | `vram_gb` | 47 | 100% |
| gpu | 47 | `memory_type` | 47 | 100% |
| gpu | 47 | `gpu_vendor` | 47 | 100% |
| cpu | 47 | `family` | 46 | 98% |
| cpu | 47 | `socket` | 47 | 100% |
| cpu | 47 | `base_clock_ghz` | 32 | 68% |
| cpu | 47 | `cache_mb` | 46 | 98% |
| motherboard | 48 | `chipset` | 48 | 100% |
| motherboard | 48 | `socket` | 48 | 100% |
| motherboard | 48 | `form_factor` | 48 | 100% |
| motherboard | 48 | `memory_type` | 48 | 100% |
| memory | 48 | `memory_type` | 48 | 100% |
| memory | 48 | `capacity_gb` | 48 | 100% |
| memory | 48 | `modules` | 48 | 100% |
| memory | 48 | `speed_mhz` | 45 | 94% |
| memory | 48 | `cas_latency` | 47 | 98% |
| storage | 48 | `capacity_gb` | 48 | 100% |
| storage | 48 | `interface` | 47 | 98% |
| storage | 48 | `form_factor` | 47 | 98% |
| storage | 48 | `pcie_gen` | 21 | 44% |
| psu | 48 | `wattage_w` | 48 | 100% |
| psu | 48 | `efficiency` | 47 | 98% |
| psu | 48 | `atx_version` | 44 | 92% |
| psu | 48 | `form_factor` | 47 | 98% |
| case | 46 | `form_factor` | 33 | 72% |
| case | 46 | `color` | 46 | 100% |

## Values parsed from product pages (data sheet)

- Components matched to a product page: **330**
- Fields filled in from the data sheet: 2205 (114 gaps in the name-based specs closed)
- Guessed values replaced by parsed ones: 87
- CPU sockets now parsed instead of inferred: 43

Each such field is recorded in the component's `spec_sources` as `parsed_product_page`. It comes from the shop's own data sheet for that exact product, not from the product name.

## Products needing review (fewest specs found)

- **psu** — `Thermalright SG 1000W` — missing: efficiency, atx_version, form_factor
- **storage** — `Seagate IronWolf Pro ST10000NT001 sisäinen kiintolevy 3.5" 10000 GB` — missing: interface, pcie_gen
- **storage** — `Samsung 2TB 9100 PRO` — missing: form_factor, pcie_gen
- **cpu** — `AMD Ryzen 5 5600XT suoritin Laatikko` — missing: base_clock_ghz, cache_mb
- **storage** — `Western Digital Red Plus WD60EFPX sisäinen kiintolevy 3.5" 6000 GB Serial ATA II` — missing: pcie_gen
- **storage** — `Western Digital Red Plus WD40EFPX sisäinen kiintolevy 3.5" 4000 GB Serial ATA II` — missing: pcie_gen
- **storage** — `Western Digital Red Plus WD20EFPX sisäinen kiintolevy 3.5" 2 TB SATA` — missing: pcie_gen
- **storage** — `Western Digital Blue SA510 2.5" 1000 GB Serial ATA III` — missing: pcie_gen
- **storage** — `Verbatim Vi550 S3 2.5" 512 GB Serial ATA III` — missing: pcie_gen
- **psu** — `Seasonic FOCUS SGX-750 (2021) virtalähdeyksikkö 750 W 20+4 pin ATX SFX Musta` — missing: atx_version
- **psu** — `Seasonic CORE BC-650 virtalähdeyksikkö 650 W 20+4 pin ATX ATX musta` — missing: atx_version
- **storage** — `Seagate IronWolf ST8000VN004 sisäinen kiintolevy 3.5" 8000 GB Serial ATA III` — missing: pcie_gen
- **storage** — `Seagate IronWolf ST4000VN006 sisäinen kiintolevy 3.5" 4000 GB Serial ATA III` — missing: pcie_gen
- **storage** — `Seagate Barracuda ST8000DM004 sisäinen kiintolevy 3.5" 8000 GB Serial ATA III` — missing: pcie_gen
- **storage** — `Seagate Barracuda ST4000DM004 sisäinen kiintolevy 3.5" 4000 GB Serial ATA III` — missing: pcie_gen

## Rows excluded as non-components

2 scraped rows were not hardware (assembly services or accessories the shop lists inside a component category). They are kept in `excluded_non_components.json` but must never reach the compatibility engine.

- `AMD Ryzen 7 7800X3D suoritin 4,2 GHz 96 MB L3 TRAY Kasauspalveluun`
- `BenQ ScreenBar Halo 2 Näytön valo Harmaa`

## Sanity check

- Component listings with a price: 334
- Median price: 173.90 €
- Min 24.90 € / max 13349.00 €

