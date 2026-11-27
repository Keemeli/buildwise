# Normalisation report — 2026-11-27

Scanned 4583 raw products from `data/raw/`, produced **3934 unique components** (547 duplicate rows merged).

Missing values are reported, not filled. A `null` spec means the shop's product name does not contain that information.

## Product identity grouping

Cross-retailer groups require every pair to match validated identifiers. Titles alone do not merge listings. See `identity_matches.json` for source evidence, contradictions and ambiguous groups.

- review: 99 components
- unresolved: 3835 components
- Conflicting product-page fields retained as null: 1; values and source URLs remain in each component’s `spec_conflicts`.

## Standardised GPU specification values

862 component fields use recognised common wording. Original values, canonical values and source details remain in `spec_observations`; unknown wording is not guessed. PCIe lane counts are retained when published, and contradictory details remain null.

## Coverage per category

| Category | Components | Field | Parsed | Coverage |
|---|---|---|---|---|
| gpu | 539 | `chipset` | 431 | 80% |
| gpu | 539 | `vram_gb` | 520 | 96% |
| gpu | 539 | `memory_type` | 522 | 97% |
| gpu | 539 | `gpu_vendor` | 534 | 99% |
| cpu | 167 | `family` | 108 | 65% |
| cpu | 167 | `socket` | 161 | 96% |
| cpu | 167 | `base_clock_ghz` | 109 | 65% |
| cpu | 167 | `cache_mb` | 163 | 98% |
| motherboard | 643 | `chipset` | 639 | 99% |
| motherboard | 643 | `socket` | 613 | 95% |
| motherboard | 643 | `form_factor` | 621 | 97% |
| motherboard | 643 | `memory_type` | 628 | 98% |
| memory | 740 | `memory_type` | 730 | 99% |
| memory | 740 | `capacity_gb` | 739 | 100% |
| memory | 740 | `modules` | 700 | 95% |
| memory | 740 | `speed_mhz` | 657 | 89% |
| memory | 740 | `cas_latency` | 638 | 86% |
| storage | 562 | `capacity_gb` | 558 | 99% |
| storage | 562 | `interface` | 535 | 95% |
| storage | 562 | `form_factor` | 533 | 95% |
| storage | 562 | `pcie_gen` | 256 | 46% |
| psu | 664 | `wattage_w` | 642 | 97% |
| psu | 664 | `efficiency` | 594 | 89% |
| psu | 664 | `atx_version` | 456 | 69% |
| psu | 664 | `form_factor` | 588 | 89% |
| case | 619 | `form_factor` | 411 | 66% |
| case | 619 | `color` | 585 | 95% |

## Facet vocabulary (values a UI filter would offer)

- **gpu.gpu_vendor**: NVIDIA ×385, AMD ×122, Intel ×27
- **gpu.memory_type**: GDDR7 ×293, GDDR6 ×215, GDDR5 ×7, GDDR4 ×4, GDDR3 ×3
- **cpu.socket**: LGA1700 ×42, AM5 ×36, AM4 ×21, LGA1851 ×15, SP5 ×13, STR5 ×13
- **motherboard.memory_type**: DDR5 ×510, DDR4 ×117, DDR3 ×2
- **motherboard.socket**: AM5 ×279, LGA1700 ×131, LGA1851 ×125, AM4 ×65, STR5 ×5, LGA4677 ×3
- **motherboard.form_factor**: ATX ×283, mikro ATX ×271, Mini ITX ×31, Micro-ATX ×13, Laajennettu ATX ×13, EEB ×3
- **memory.memory_type**: DDR5 ×466, DDR4 ×237, DDR3 ×26, DDR2 ×1
- **memory.speed_mhz**: 3200 ×139, 6000 ×124, 5600 ×112, 6400 ×51, 4800 ×46, 2666 ×35
- **storage.interface**: SATA III ×197, PCI Express 4.0 ×149, PCI Express 5.0 ×63, SATA ×39, PCI Express 3.0 ×35, SAS ×22
- **storage.form_factor**: M.2 2280 ×148, M.2 ×129, 3.5" ×128, 2.5" ×115, M.2 2242 ×5, M.2 2230 ×5
- **psu.efficiency**: 80 PLUS Gold ×153, 90% ×90, 80 PLUS Bronze ×63, 80 PLUS Platinum ×62, 85% ×32, 92% ×29
- **case.tower_size**: Midi Tower ×307, Mini Tower ×59, Tower ×53, Micro Tower ×34, Full Tower ×30, Small Form Factor (SFF) ×11

## Values parsed from product pages (data sheet)

- Components matched to a product page: **3558**
- Fields filled in from the data sheet: 23022 (1890 gaps in the name-based specs closed)
- Guessed values replaced by parsed ones: 414
- CPU sockets now parsed instead of inferred: 100
- Storage capacities left unknown because the name and the data sheet disagree: 1

Each such field is recorded in the component's `spec_sources` as `parsed_product_page`. It comes from the shop's own data sheet for that exact product, not from the product name.

## Price conflicts requiring inspection

- **Datatronic** — https://datatronic.fi/komponentit/prosessorit/amd-ryzen-threadripper-pro-5965wx-suoritin-38-ghz-128-mb-l3-laatikko-amd-100-100000446wof — current price unknown
  - 268900 cents at 2026-11-12T14:45:42+00:00 — source: {'source_file': 'datatronic_cpu_p5_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/prosessorit?page=5', 'raw_html': 'data/raw/html/datatronic_cpu_p5_2026-11-12_59b9b4a1e94c.html', 'origin': None, 'run_id': None, 'extraction': None}
  - 733900 cents at 2026-11-12T14:45:42+00:00 — source: {'source_file': 'datatronic_cpu_p5_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/prosessorit?page=5', 'raw_html': 'data/raw/html/datatronic_cpu_p5_2026-11-12_59b9b4a1e94c.html', 'origin': None, 'run_id': None, 'extraction': None}
- **Datatronic** — https://datatronic.fi/komponentit/naytonohjaimet/asus-gt730-sl-2gd5-brk-nvidia-geforce-gt-730-2-gb-gddr5-asus-90yv06n2-m0na00 — current price unknown
  - 10990 cents at 2026-11-12T14:45:22+00:00 — source: {'source_file': 'datatronic_gpu_p14_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/naytonohjaimet?page=14', 'raw_html': 'data/raw/html/datatronic_gpu_p14_2026-11-12_7c8fa99c8ee0.html', 'origin': None, 'run_id': None, 'extraction': None}
  - 8290 cents at 2026-11-12T14:45:22+00:00 — source: {'source_file': 'datatronic_gpu_p14_2026-11-12.json', 'source_type': None, 'source_url': 'https://datatronic.fi/naytonohjaimet?page=14', 'raw_html': 'data/raw/html/datatronic_gpu_p14_2026-11-12_7c8fa99c8ee0.html', 'origin': None, 'run_id': None, 'extraction': None}

## Products needing review (fewest specs found)

- **storage** — `WD BLACK SN8100 SED ATA` — missing: capacity_gb, interface, form_factor, pcie_gen
- **storage** — `Seagate ST10000VN000 sisäinen kiintolevy` — missing: capacity_gb, interface, form_factor, pcie_gen
- **psu** — `SS-500L1U Bulk (grau 500 Watt Bulk)` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `SAMA G850 virtalähdeyksikkö` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `MSI Netzteil PRO A1000PL PCI5 1000Watt` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `MSI Netzteil MAG A750BN PCIE5 III 750Watt` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `MSI Netzteil MAG A650BN PCIE5 III 650Watt` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `MSI Netzteil MAG A1200PLS PCI5 1200Watt` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `MSI Netzteil MAG A1000PLS PCI5 1000Watt` — missing: wattage_w, efficiency, atx_version, form_factor
- **memory** — `Goodram GR00C5-64L52S/16G muistimoduuli` — missing: memory_type, capacity_gb, modules, speed_mhz
- **psu** — `GAMER STORM PS850P (schwarz 1x 12 Pin High Power GPU 3x PCIe Kabelmanagement 850` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `GAMER STORM PS1000P (schwarz 1x 12 Pin High Power GPU 3x PCIe Kabelmanagement 10` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `GAMER STORM PF750L (schwarz 2x PCIe 750 Watt)` — missing: wattage_w, efficiency, atx_version, form_factor
- **psu** — `GAMER STORM PF650L (schwarz 2x PCIe 650 Watt)` — missing: wattage_w, efficiency, atx_version, form_factor
- **memory** — `G.Skill F5-6000J2836G32GX2-RS5W muistimoduuli 64 GB` — missing: memory_type, modules, speed_mhz, cas_latency

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

94 scraped rows do not belong to the shop category they were found in. They are listed in `excluded_category_mismatch.json` with a reason: `accessory` (the product type in the name is a cooler, fan, cable, ...), `unverifiable` (no category-defining value and no sign of the category in the name) or `form_factor` (a parsed value that cannot belong to the category).

### `accessory` — 92

- **case** — `Cooler Master Hyper 612 APEX Suoritin Ilmanjäähdytin 12 cm musta 1 kpl`
- **case** — `HAVN HVN-FS-H1230-01-TRI Tietokoneen jäähdytysjärjestelmä Tietokonekotelo Tuulet`
- **case** — `HAVN HVN-FS-H1230-01 Tietokoneen jäähdytysjärjestelmä Tietokonekotelo Tuuletin 1`
- **case** — `Phanteks PH-MLEDKT6_BK01 tietokonekotelon osa Näyttö`
- **case** — `SAMA Gears A40L Suoritin Ilmanjäähdytin 12 cm Valkoinen 1 kpl`
- **case** — `Gamiac TKL90G - White/Red - TKL - Kailh Blue`
- **case** — `DeepCool FL12R Tietokonekotelo Tuuletin 12 cm musta 1 kpl`
- **case** — `Phanteks PH-MLEDKT6_WT01 tietokonekotelon osa Näyttö`
- **cpu** — `Intel Wireless-N 7260 Plus Bluetooth Sisäinen WLAN / Bluetooth 300 Mbit/s`
- **gpu** — `NZXT AB-RH175-B1 tietokonekotelon osa Universaali Grafiikkakortin pidike`

### `unverifiable` — 2

- **cpu** — `K DeepCool AG300 G2`
- **storage** — `Seagate Storage Expansion Card Tallennuksen laajennuskortti`

## Rows moved to the category their name states

22 scraped rows name a product type of another category we carry (a power supply on a storage page) and nothing in the name points to the page's category. They are parsed as the named category.

- gpu → **case** — `NZXT H9 Flow RGB Midi Tower musta`
- gpu → **case** — `NZXT H9 Flow Midi Tower musta`
- gpu → **case** — `NZXT H9 Flow RGB+ Midi Tower musta`
- memory → **storage** — `XPG Spectrix S65G 500GB (aluminium PCIe 4.0 x4 M.2 2280)`
- memory → **storage** — `XPG SPECTRIX S65G 1 TB M.2 PCI Express 4.0 NVMe 3D NAND`
- memory → **storage** — `ADATA SMAR-980B-1TCS SSD-massamuisti 1 TB M.2 PCI Express 5.0 NVMe 3D NAND`
- memory → **case** — `Jonsbo D32 PRO Midi Tower musta`
- motherboard → **gpu** — `Asrock AMD Radeon RX 9060 XT Challenger 16GB OC GDDR6`
- motherboard → **psu** — `ASUS TUF Gaming 650W Gold EVO PSU`
- psu → **case** — `Thermaltake AX500 Full Tower musta`
- psu → **case** — `Thermaltake AX500 Full Tower Valkoinen`
- storage → **psu** — `DeepCool PN750M virtalähdeyksikkö 750 W 20+4 pin ATX ATX musta`
- storage → **motherboard** — `ASUS B850M MAX GAMING WIFI AMD B850 Pistoke AM5 mikro ATX`
- storage → **motherboard** — `MSI MEG X870E GODLIKE emolevy AMD X870E Pistoke AM5 Laajennettu ATX`
- storage → **motherboard** — `GIGABYTE B550 EAGLE WIFI6 emolevy`

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

- Component listings with a price: 3886
- Median price: 230.40 €
- Min 20.90 € / max 53405.00 €

