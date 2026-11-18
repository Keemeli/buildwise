# Product-page data sheet report — 2026-11-12

Fetched **3869** product pages; **3607** parsed successfully, 262 failed.

Values here are **parsed from the shop's own data sheet**, not inferred from the product name. Unmapped labels are listed below instead of being guessed.

## Product identifier evidence

Identity inspected on 3864 saved product pages; GTIN on 3844, manufacturer part number on 3850.
Identifiers are retained as evidence; listings are not matched or merged by them yet.

- https://datatronic.fi/komponentit/kotelot/lc-power-lc-1400mi-300sfx-tietokonekotelo-micro-tower-musta-lc-power — manufacturer_part_number:missing_or_placeholder
- https://datatronic.fi/komponentit/prosessorit/amd-3500x-prosessori-konekasaukseen-100-000000158 — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/prosessorit/amd-ryzen-threadripper-pro-5965wx-suoritin-38-ghz-128-mb-l3-laatikko-amd-100-100000446wof — source_product_identity_conflict
- https://datatronic.fi/komponentit/naytonohjaimet/nzxt-ab-rh175-w1-tietokonekotelon-osa-universaali-grafiikkakortin-pidike-nzxt-ab-rh175-w1 — source_product_identity_conflict
- https://datatronic.fi/komponentit/naytonohjaimet/asus-gt730-sl-2gd5-brk-nvidia-geforce-gt-730-2-gb-gddr5-asus-90yv06n2-m0na00 — source_product_identity_conflict
- https://datatronic.fi/komponentit/naytonohjaimet/pny-geforce-rtx-5070-ti-oc-nvidia-16-gb-gddr7-pny-vcg5070t16tfxpb1-o — source_product_identity_conflict
- https://datatronic.fi/komponentit/naytonohjaimet/nvidia-rtx-pro-4500-blackwell-server-edition-32gb-gddr7-900-2g147-0000-000 — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/naytonohjaimet/b-stock-palit-geforce-rtx-3050-stormx-6gb-nvidia-gddr6-palit-ne63050018je-1072f — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/muistit/b-stock-crucial-ct16g48c40s5-muistimoduuli-16-gb-1-x-16-gb-ddr5-262-pin-so-dimm-crucial-ct16g48c40s5 — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/muistit/kingston-technology-kcp432ss6-4-muistimoduuli-4-gb-1-x-4-gb-ddr4-3200-mhz-kingston-technology — manufacturer_part_number:missing_or_placeholder
- https://datatronic.fi/komponentit/emolevyt/b-stock-gigabyte-b850-aorus-elite-wifi7-amd-b850-pistoke-am5-atx-gigabyte-b850-a-elite-wf7 — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/emolevyt/asus-rog-strix-b760-g-gaming-wifi-intel-b760-lga-1700-mikro-atx-asus-90mb1eq0-m1eay0 — source_product_identity_conflict
- https://datatronic.fi/komponentit/emolevyt/asus-prime-b760m-a-wifi-intel-b760-lga-1700-mikro-atx-asus-90mb1el0-m1eay0 — source_product_identity_conflict
- https://datatronic.fi/komponentit/emolevyt/b840m-d3hp-b840m-d3hp — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/virtalahteet/seasonic-prime-fanless-tx-virtalahdeyksikko-700-w-20-4-pin-atx-atx-musta-seasonic-prime-tx-700 — source_product_identity_conflict
- https://datatronic.fi/komponentit/virtalahteet/b-stock-be-quiet-dark-power-14-1200-w-80-plus-titanium-virtalahdeyksikko-20-4-pin-atx-atx-musta-be-quiet-bp021eu — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/virtalahteet/b-stock-seasonic-core-bc-650-virtalahdeyksikko-650-w-20-4-pin-atx-atx-musta-seasonic-srp-cbc651-a5a51jf — source_product_identity_conflict
- https://datatronic.fi/komponentit/virtalahteet/b-stock-be-quiet-pure-power-13-m-550w-virtalahdeyksikko-20-4-pin-atx-atx-musta-be-quiet-bp024eu — gtin:invalid_check_digit
- https://datatronic.fi/komponentit/kiintolevyt-ssd-levyt/ssd/msi-meg-x870e-godlike-emolevy-amd-x870e-pistoke-am5-laajennettu-atx-msi-7e48-001r — source_product_identity_conflict

## Coverage per category and field

| Category | Products | Field | Parsed | Coverage |
|---|---|---|---|---|
| gpu | 474 | `power_w` | 150 | ❌ 32% |
| gpu | 474 | `length_mm` | 352 | ⚠️ 74% |
| gpu | 474 | `width_mm` | 332 | ⚠️ 70% |
| gpu | 474 | `height_mm` | 388 | ✅ 82% |
| gpu | 474 | `slot_width` | 324 | ⚠️ 68% |
| gpu | 474 | `power_connectors` | 329 | ⚠️ 69% |
| gpu | 474 | `recommended_psu_w` | 329 | ⚠️ 69% |
| gpu | 474 | `interface` | 411 | ✅ 87% |
| gpu | 474 | `vram_gb` | 412 | ✅ 87% |
| gpu | 474 | `memory_type` | 411 | ✅ 87% |
| gpu | 474 | `graphics_chipset` | 411 | ✅ 87% |
| gpu | 474 | `memory_bus_bit` | 404 | ✅ 85% |
| cpu | 170 | `tdp_w` | 163 | ✅ 96% |
| cpu | 170 | `max_turbo_power_w` | 57 | ❌ 34% |
| cpu | 170 | `socket` | 158 | ✅ 93% |
| cpu | 170 | `memory_types` | 155 | ✅ 91% |
| cpu | 170 | `cores` | 161 | ✅ 95% |
| cpu | 170 | `threads` | 160 | ✅ 94% |
| cpu | 170 | `cache_mb` | 163 | ✅ 96% |
| cpu | 170 | `base_clock_mhz` | 108 | ⚠️ 64% |
| cpu | 170 | `boost_clock_mhz` | 154 | ✅ 91% |
| cpu | 170 | `memory_channels` | 125 | ⚠️ 74% |
| cpu | 170 | `memory_speed_mhz` | 88 | ⚠️ 52% |
| cpu | 170 | `integrated_graphics` | 163 | ✅ 96% |
| cpu | 170 | `cooler_included` | 96 | ⚠️ 56% |
| cpu | 170 | `lithography_nm` | 59 | ❌ 35% |
| cpu | 170 | `pcie_version` | 147 | ✅ 86% |
| motherboard | 645 | `socket` | 602 | ✅ 93% |
| motherboard | 645 | `chipset` | 598 | ✅ 93% |
| motherboard | 645 | `form_factor` | 597 | ✅ 93% |
| motherboard | 645 | `memory_type` | 600 | ✅ 93% |
| motherboard | 645 | `memory_slots` | 600 | ✅ 93% |
| motherboard | 645 | `memory_max_gb` | 599 | ✅ 93% |
| motherboard | 645 | `memory_channels` | 574 | ✅ 89% |
| motherboard | 645 | `m2_slots` | 545 | ✅ 84% |
| motherboard | 645 | `width_mm` | 594 | ✅ 92% |
| motherboard | 645 | `depth_mm` | 595 | ✅ 92% |
| memory | 751 | `memory_type` | 690 | ✅ 92% |
| memory | 751 | `capacity_gb` | 700 | ✅ 93% |
| memory | 751 | `modules` | 687 | ✅ 91% |
| memory | 751 | `speed_mhz` | 566 | ⚠️ 75% |
| memory | 751 | `cas_latency` | 613 | ✅ 82% |
| memory | 751 | `form_factor` | 0 | ❌ 0% |
| memory | 751 | `voltage_v` | 643 | ✅ 86% |
| memory | 751 | `ecc` | 513 | ⚠️ 68% |
| storage | 574 | `capacity_gb` | 534 | ✅ 93% |
| storage | 574 | `interface` | 524 | ✅ 91% |
| storage | 574 | `form_factor` | 158 | ❌ 28% |
| storage | 574 | `pcie_gen` | 0 | ❌ 0% |
| storage | 574 | `nvme` | 327 | ⚠️ 57% |
| storage | 574 | `read_mb_s` | 373 | ⚠️ 65% |
| storage | 574 | `write_mb_s` | 362 | ⚠️ 63% |
| psu | 647 | `wattage_w` | 570 | ✅ 88% |
| psu | 647 | `efficiency` | 560 | ✅ 87% |
| psu | 647 | `atx_version` | 448 | ⚠️ 69% |
| psu | 647 | `form_factor` | 0 | ❌ 0% |
| psu | 647 | `length_mm` | 439 | ⚠️ 68% |
| psu | 647 | `width_mm` | 537 | ✅ 83% |
| psu | 647 | `depth_mm` | 537 | ✅ 83% |
| psu | 647 | `height_mm` | 536 | ✅ 83% |
| psu | 647 | `modular` | 438 | ⚠️ 68% |
| psu | 647 | `fan_size_mm` | 495 | ⚠️ 77% |
| psu | 647 | `main_connector` | 544 | ✅ 84% |
| psu | 647 | `pcie_connectors` | 460 | ⚠️ 71% |
| case | 608 | `max_gpu_length_mm` | 509 | ✅ 84% |
| case | 608 | `max_cooler_height_mm` | 526 | ✅ 87% |
| case | 608 | `max_psu_length_mm` | 424 | ⚠️ 70% |
| case | 608 | `supported_motherboards` | 561 | ✅ 92% |
| case | 608 | `tower_size` | 518 | ✅ 85% |
| case | 608 | `width_mm` | 560 | ✅ 92% |
| case | 608 | `height_mm` | 560 | ✅ 92% |
| case | 608 | `depth_mm` | 560 | ✅ 92% |
| case | 608 | `expansion_slots` | 480 | ⚠️ 79% |
| case | 608 | `color` | 575 | ✅ 95% |
| case | 608 | `material` | 461 | ⚠️ 76% |
| case | 608 | `psu_included` | 452 | ⚠️ 74% |
| case | 608 | `hdd_35_bays` | 535 | ✅ 88% |
| case | 608 | `front_usb_c` | 371 | ⚠️ 61% |

## Labels we could not map (top 25)

These are preserved for review — add them to the selected retailer specification field map when they matter for a compatibility rule.

-  750× memory: Varastossa
-  677× memory: Komponentti (tuotteelle)
-  646× psu: Varastossa
-  643× motherboard: Varastossa
-  607× case: Varastossa
-  606× motherboard: Suoritinvalmistaja
-  603× motherboard: Komponentti (tuotteelle)
-  598× motherboard: Ethernet LAN
-  597× motherboard: Ethernet LAN (RJ-45) -portit
-  597× motherboard: Tuetut tallennusasemaliitännät
-  596× motherboard: USB 2.0-liittimet
-  593× motherboard: HDMI-porttien lukumäärä
-  591× motherboard: Wi-Fi
-  590× motherboard: USB 3.2 Gen 1 (3.1 Gen 1) liittimet
-  589× motherboard: Muistipaikkojen tyyppi
-  587× motherboard: Ethernet-liitännän tyyppi
-  586× motherboard: Äänilähdön kanavat
-  580× memory: Muisti
-  576× case: Malli
-  576× motherboard: SATA III-liittimiä
-  576× motherboard: Emolevyn piirisarja
-  575× motherboard: USB 2.0 -porttien määrä
-  571× storage: Varastossa
-  563× motherboard: USB 3.2 (3.1 sukupolvi 1) A-tyypin porttien määrä
-  561× psu: Tarkoitus

## Failed pages

- **cpu** `AMD Ryzen 5 5600XT suoritin Laatikko` — no supported specification fields parsed
- **psu** `Thermalright SG 1000W` — no supported specification fields parsed
- **case** `Lian Li A3 Wood Black glass version` — no supported specification fields parsed
- **case** `HYTE X50 MID TOWER CASE MATCHA MILK` — no supported specification fields parsed
- **case** `Fractal Design Fractal Epoche XL Weiss TG` — no supported specification fields parsed
- **case** `SAMA SV-01 Black ATX Mid-tower Case` — no supported specification fields parsed
- **case** `ASUS TEK COMPUTER` — no supported specification fields parsed
- **case** `HYTE X50 AIR MID TOWER CASE SNOW WHITE` — no supported specification fields parsed
- **case** `HYTE X50 MID TOWER CASE STRAWBERRY MILK` — no supported specification fields parsed
- **case** `HYTE X50 MID TOWER CASE CHERRY` — no supported specification fields parsed
- **case** `ASUS ProArt PA602 Wood Edition Retro Brown - Tempered Glass ` — no supported specification fields parsed
- **case** `HYTE X50 AIR MID TOWER CASE PITCH BLACK` — no supported specification fields parsed
- **case** `Antec C6 Curve Air White` — no supported specification fields parsed
- **case** `NZXT H6 RGB+ Compact Dual-chamber ATX Case White With RGB Fa` — no supported specification fields parsed
- **case** `NZXT H6 RGB+ Compact Dual-chamber ATX Case Black With RGB Fa` — no supported specification fields parsed
- **case** `Jonsbo V12 PC-Chassi Mini-Tower Micro-ATX - White` — no supported specification fields parsed
- **case** `NZXT H6 Compact Dual-chamber ATX Case All White` — no supported specification fields parsed
- **case** `FRAME 4000X RS White` — no supported specification fields parsed
- **case** `HAVN HS 360 VGPU White` — no supported specification fields parsed
- **case** `HAVN HS 360 Black` — no supported specification fields parsed

