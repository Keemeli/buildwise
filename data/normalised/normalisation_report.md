# Normalisation report — 2026-11-12

Scanned 4583 raw products from `data/raw/`, produced **4024 unique components** (546 duplicate rows merged).

Missing values are reported, not filled. A `null` spec means the shop's product name does not contain that information.

## Product identity grouping

Cross-retailer groups require every pair to match validated identifiers. Titles alone do not merge listings. See `identity_matches.json` for source evidence, contradictions and ambiguous groups.

- review: 196 components
- unresolved: 3828 components

## Standardised GPU specification values

862 component fields use recognised common wording. Original values, canonical values and source details remain in `spec_observations`; unknown wording is not guessed. PCIe lane counts are retained when published, and contradictory details remain null.

## Coverage per category

| Category | Components | Field | Parsed | Coverage |
|---|---|---|---|---|
| gpu | 577 | `chipset` | 431 | 75% |
| gpu | 577 | `vram_gb` | 520 | 90% |
| gpu | 577 | `memory_type` | 521 | 90% |
| gpu | 577 | `gpu_vendor` | 534 | 93% |
| cpu | 171 | `family` | 108 | 63% |
| cpu | 171 | `socket` | 161 | 94% |
| cpu | 171 | `base_clock_ghz` | 109 | 64% |
| cpu | 171 | `cache_mb` | 163 | 95% |
| motherboard | 651 | `chipset` | 637 | 98% |
| motherboard | 651 | `socket` | 611 | 94% |
| motherboard | 651 | `form_factor` | 619 | 95% |
| motherboard | 651 | `memory_type` | 627 | 96% |
| memory | 760 | `memory_type` | 731 | 96% |
| memory | 760 | `capacity_gb` | 744 | 98% |
| memory | 760 | `modules` | 700 | 92% |
| memory | 760 | `speed_mhz` | 657 | 86% |
| memory | 760 | `cas_latency` | 638 | 84% |
| storage | 581 | `capacity_gb` | 559 | 96% |
| storage | 581 | `interface` | 540 | 93% |
| storage | 581 | `form_factor` | 535 | 92% |
| storage | 581 | `pcie_gen` | 254 | 44% |
| psu | 664 | `wattage_w` | 639 | 96% |
| psu | 664 | `efficiency` | 592 | 89% |
| psu | 664 | `atx_version` | 455 | 69% |
| psu | 664 | `form_factor` | 586 | 88% |
| case | 620 | `form_factor` | 404 | 65% |
| case | 620 | `color` | 585 | 94% |

## Facet vocabulary (values a UI filter would offer)

- **gpu.gpu_vendor**: NVIDIA ×386, AMD ×121, Intel ×27
- **gpu.memory_type**: GDDR7 ×293, GDDR6 ×214, GDDR5 ×7, GDDR4 ×4, GDDR3 ×3
- **cpu.socket**: LGA1700 ×42, AM5 ×36, AM4 ×21, LGA1851 ×15, SP5 ×13, STR5 ×13
- **motherboard.memory_type**: DDR5 ×508, DDR4 ×117, DDR3 ×2, GDDR6 ×1
- **motherboard.socket**: AM5 ×277, LGA1700 ×131, LGA1851 ×125, AM4 ×65, STR5 ×5, LGA4677 ×3
- **motherboard.form_factor**: ATX ×282, mikro ATX ×271, Mini ITX ×31, Laajennettu ATX ×13, Micro-ATX ×12, EEB ×3
- **memory.memory_type**: DDR5 ×466, DDR4 ×238, DDR3 ×26, DDR2 ×1
- **memory.speed_mhz**: 3200 ×139, 6000 ×124, 5600 ×112, 6400 ×51, 4800 ×46, 2666 ×35
- **storage.interface**: SATA III ×197, PCI Express 4.0 ×149, PCI Express 5.0 ×63, SATA ×40, PCI Express 3.0 ×35, SAS ×22
- **storage.form_factor**: M.2 2280 ×147, M.2 ×132, 3.5" ×128, 2.5" ×115, M.2 2242 ×5, M.2 2230 ×5
- **psu.efficiency**: 80 PLUS Gold ×153, 90% ×90, 80 PLUS Bronze ×63, 80 PLUS Platinum ×62, 85% ×32, 92% ×29
- **case.tower_size**: Midi Tower ×307, Mini Tower ×59, Tower ×53, Micro Tower ×34, Full Tower ×30, Small Form Factor (SFF) ×11

## Values parsed from product pages (data sheet)

- Components matched to a product page: **3604**
- Fields filled in from the data sheet: 23102 (1912 gaps in the name-based specs closed)
- Guessed values replaced by parsed ones: 414
- CPU sockets now parsed instead of inferred: 100

Each such field is recorded in the component's `spec_sources` as `parsed_product_page`. It comes from the shop's own data sheet for that exact product, not from the product name.

## Price conflicts requiring inspection

- **Datatronic** — https://datatronic.fi/komponentit/prosessorit/amd-ryzen-threadripper-pro-5965wx-suoritin-38-ghz-128-mb-l3-laatikko-amd-100-100000446wof — current price unknown
  - 268900 cents at 2026-11-12T14:45:42+00:00 — source: {'source_file': 'datatronic_cpu_p5_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/prosessorit?page=5', 'raw_html': 'data/raw/html/datatronic_cpu_p5_2026-11-12_59b9b4a1e94c.html', 'origin': None, 'run_id': None, 'extraction': None}
  - 733900 cents at 2026-11-12T14:45:42+00:00 — source: {'source_file': 'datatronic_cpu_p5_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/prosessorit?page=5', 'raw_html': 'data/raw/html/datatronic_cpu_p5_2026-11-12_59b9b4a1e94c.html', 'origin': None, 'run_id': None, 'extraction': None}
- **Datatronic** — https://datatronic.fi/komponentit/naytonohjaimet/asus-gt730-sl-2gd5-brk-nvidia-geforce-gt-730-2-gb-gddr5-asus-90yv06n2-m0na00 — current price unknown
  - 10990 cents at 2026-11-12T14:45:22+00:00 — source: {'source_file': 'datatronic_gpu_p14_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/naytonohjaimet?page=14', 'raw_html': 'data/raw/html/datatronic_gpu_p14_2026-11-12_7c8fa99c8ee0.html', 'origin': None, 'run_id': None, 'extraction': None}
  - 8290 cents at 2026-11-12T14:45:22+00:00 — source: {'source_file': 'datatronic_gpu_p14_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/naytonohjaimet?page=14', 'raw_html': 'data/raw/html/datatronic_gpu_p14_2026-11-12_7c8fa99c8ee0.html', 'origin': None, 'run_id': None, 'extraction': None}

## Products needing review (fewest specs found)

- **memory** — `Xilence XZ107 liitäntäkortti/-sovitin Sisäinen PCIe` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Noctua NF-A6X15 PWM Tietokoneen jäähdytysjärjestelmä Tietokonekotelo Tuuletin 6 ` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Noctua NF-A6X15 FLX Tietokoneen jäähdytysjärjestelmä Tietokonekotelo Tuuletin 6 ` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Noctua NF-A6X15 5V Tietokoneen jäähdytysjärjestelmä Tietokonekotelo Tuuletin 6 c` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Noctua NA-SC1 SX2 Tietokoneen jäähdytysjärjestelmän osa ja lisätarvike Kaapeliso` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Moza Racing RS073 Polkimen kiinnityslevy` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Montech HP140 ARGB PWM Tietokonekotelo Tuuletin 14 cm Valkoinen 3 kpl` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Montech HP140 ARGB PWM Tietokonekotelo Tuuletin 14 cm Valkoinen 3 kpl` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Jonsbo D32 PRO Midi Tower musta` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `GIGABYTE TPM-Module - Trusted Platform` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Display 14.0 FHD IPS AG` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Creative Labs Sound Blaster GS5 musta Langallinen & langaton 30 W` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Core Geforce RTX 5080/5070Ti TUF Gaming (mit Backplate)` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `CORSAIR VENGEANCE Enhancement Kit Black` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency
- **memory** — `Alphacool 25667 Tietokoneen jäähdytysjärjestelmän osa ja lisätarvike Vesiblokki` — missing: memory_type, capacity_gb, modules, speed_mhz, cas_latency

## Rows excluded as non-components

8 scraped rows were not hardware (assembly services or accessories the shop lists inside a component category). They are kept in `excluded_non_components.json` but must never reach the compatibility engine.

- `AMD Ryzen 7 7800X3D suoritin 4,2 GHz 96 MB L3 TRAY Kasauspalveluun`
- `AMD Ryzen 7 7800X3D suoritin 4,2 GHz 96 MB L3 TRAY Kasauspalveluun`
- `AMD Ryzen 7 7800X3D suoritin 4,2 GHz 96 MB L3 TRAY Kasauspalveluun`
- `BenQ ScreenBar Halo 2 Näytön valo Harmaa`
- `BenQ ScreenBar Halo 2 Näytön valo Harmaa`
- `BenQ ScreenBar Halo 2 Näytön valo Harmaa`
- `Mousetrapper Sleeve Näppäimistölaukku`
- `ASUS ROG Falchion Ace HFX näppäimistö Pelaaminen USB Musta`

## Rows excluded for contradicting their category

5 scraped rows carry a parsed value that cannot belong to their shop category — a motherboard on a storage page, parsed with the storage vocabulary. They are listed in `excluded_category_mismatch.json`; the category is never guessed.

- **storage** — `GIGABYTE B850M AORUS ELITE WIFI6E ICE AMD B850 Pistoke AM5 mikro ATX` (form_factor mikro ATX)
- **storage** — `GIGABYTE B850M D3HP emolevy AMD B850 Pistoke AM5 mikro ATX` (form_factor mikro ATX)
- **storage** — `MSI MEG X870E GODLIKE emolevy AMD X870E Pistoke AM5 Laajennettu ATX` (form_factor Laajennettu ATX)
- **storage** — `ASUS B850M MAX GAMING WIFI AMD B850 Pistoke AM5 mikro ATX` (form_factor mikro ATX)
- **storage** — `MSI MEG X870E GODLIKE emolevy AMD X870E Pistoke AM5 Laajennettu ATX` (form_factor Laajennettu ATX)

## Suspect categories (nothing parsed at all)

- **case** — `Antec C6 Curve Air White`
- **case** — `ASUS ProArt PA401 Wood Edition Beige - Tempered Glass Panel`
- **case** — `ASUS Proart PA401 Wood Mesh PWM Beige`
- **case** — `ASUS ProArt PA602 Wood Edition Retro Brown - Tempered Glass Panel`
- **case** — `ASUS TEK COMPUTER`
- **case** — `Chieftec UNC-209SR-B modulaarinen palvelinalusta Teline ( 2U )`
- **case** — `Cooler Master Qube Q340 White`
- **case** — `Fractal Design Fractal Epoche XL Weiss TG`
- **case** — `Fractal Design Meshify 2 Compact Lite White TG Clear`
- **case** — `Fractal Design Terra Small Form Factor (SFF) Grafiitti`

## Sanity check

- Component listings with a price: 3974
- Median price: 224.90 €
- Min 4.90 € / max 53405.00 €

