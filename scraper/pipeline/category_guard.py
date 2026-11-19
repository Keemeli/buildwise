"""Catch rows a shop filed under the wrong component category.

A row's category comes from the listing page it was scraped from, and the full Datatronic
crawl showed that the shop files all kinds of things on those pages: a Noctua cable adapter
on a memory page, fan grills and AIO coolers on graphics card pages, a power supply and a
motherboard on storage pages, floor mats on motherboard pages. Shown in the builder, those
rows are offered as a "memory module" or a "graphics card".

Datatronic names carry the Icecat product type in Finnish ("... virtalähdeyksikkö 750 W",
"... Tietokoneen jäähdytysjärjestelmän osa ja lisätarvike Kaapelisovitin"), which is a much
stronger signal than the page the row was found on. Three decisions, in this order:

1. `accessory` — the name says it is not a build component at all (cooler, fan, cable,
   thermal paste, speaker, ...). The row is excluded.
2. `move` — the name says it is a component of another category we carry, and nothing in
   it says it belongs where the shop put it. The row is parsed as that category instead.
3. `unverifiable` (after product-page specs are merged, see `lacks_identity`) — not one
   category-defining value is known and the name has no sign of the category either.

Every term below was observed in the real catalogue; the comment next to it names one.
"""
from __future__ import annotations
import re
from typing import Any, Dict, Optional, Tuple

# Not a component of a PC build, whichever category page it was found on.
ACCESSORY_TERMS = (
    r"lisätarvike",                       # Noctua NA-SC1 SX2 ... lisätarvike Kaapelisovitin
    r"tietokonekotelon osa",              # NZXT AB-RH175-B1 tietokonekotelon osa ...
    r"\btuuletin\b",                      # Montech HP140 ARGB PWM Tietokonekotelo Tuuletin
    r"tuuletusritilä", r"\bfan grills?\b",  # Noctua NA-FG1-20 Sx2 Fan Grills
    r"nesteenjäähdytin", r"ilmanjäähdytin",  # NZXT Kraken Plus 240 ... nesteenjäähdytin
    r"vesijäähdytin", r"vesiblokki", r"\bcpu-blokki\b", r"\bwater block\b",
    r"\bgpu block\b",                     # Thermal Grizzly DeltaMate GPU Block - ROG Astral RTX 5090
    r"lämpötahna", r"\bputty\b",          # Thermal Grizzly Putty Basic ... Lämpötahna
    r"\bmit backplate\b",                 # Core Geforce RTX 5080/5070Ti TUF Gaming (mit Backplate)
    r"kaiutin", r"\bsound blaster\b",     # Creative Pebble X Plus kaiutinsetti
    r"\bfloor pad\b",                     # Arozzi Zona Round Floor Pad
    r"\bac-adapter\b", r"paristolaturi",  # Lenovo AC-Adapter ADL45WCG
    r"liitäntäkortti", r"\bwlan\b",       # Xilence XZ107 liitäntäkortti/-sovitin
    r"\btpm-module\b",                    # GIGABYTE TPM-Module - Trusted Platform
    r"grafiikkakortin pidike",
    r"polkimen",                          # Moza Racing RS073 Polkimen kiinnityslevy
    r"pelikonsolin osa",                  # Seagate STJR1000400 pelikonsolin osa
    r"luokittelematon",                   # ASUS 90SB0CS0-M0UAY0 luokittelematon
    r"tallennusaseman kotelo", r"ssd-kotelo", r"\bez-adapter\b",
    r"\b5[.,]25\"? ?bay\b",               # 2x 2.5SATA HDD/SSD RAID 1 in 1x 5.25 bay
    r"\benhancement kit\b",               # CORSAIR VENGEANCE Enhancement Kit
    r"\bchromax\b", r"\bNA-SAVP?\d",      # Noctua NA-SAV2 chromax.green (anti-vibration pads)
    r"\bLGA ?\d+ Kit\b",                  # Cryorig LGA 1700 Kit Type A (cooler mount)
    r"\bTab M\d+\b",                      # Lenovo Tab M10 Plus (a tablet on a memory page)
    r"^Display \d",                       # Display 14.0 FHD IPS AG (a laptop panel)
    r"\bkailh\b",                         # Gamiac TKL90G ... Kailh Blue (a keyboard)
)
ACCESSORY_PATTERN = re.compile("|".join(ACCESSORY_TERMS), re.I)

# The product type naming one of our categories. Checked in this order.
CATEGORY_TYPE_PATTERNS = {
    "psu": re.compile(r"virtal.{1,2}hde|\bnetzteil\b|\bPSU\b|\bpower supply\b|"
                      r"\b\d{3,4} ?W\b.*\b(80\+|Bronze|Gold|Platinum|Titanium)\b", re.I),
    "motherboard": re.compile(r"emolevy|\b(pistoke|socket) (AM\d|LGA ?\d+|sTR\d|SP\d)\b", re.I),
    "case": re.compile(r"tietokonekotelo(?!n)|\b(midi|micro|mini|full)[ -]?tower\b|"
                       r"\bmid-tower\b|\bATX case\b", re.I),
    "storage": re.compile(r"\bSSD\b|ssd-massamuisti|kiintolevy|\bNVMe\b|\bM\.2 22\d0\b|"
                          r"\bSerial ATA\b", re.I),
    "gpu": re.compile(r"näytönohjain|\bgeforce\b|\bradeon rx\b|\bRTX \d{4}\b|\bArc [AB]\d{2,3}\b", re.I),
    "cpu": re.compile(r"prosessori|\bsuoritin \d|\bryzen \d|\bcore (i\d|ultra)\b|\bepyc\b|\bxeon\b", re.I),
}

# Any sign in the name that a row belongs to its own category. Broader than the type
# patterns: a name that says "AM5" or "DDR5" anywhere is not moved away.
OWN_CATEGORY_SIGNAL = {
    "cpu": re.compile(r"prosessori|suoritin|processor|ryzen|\bcore\b|epyc|xeon|threadripper|"
                      r"athlon|pentium|celeron|\bintel\b|\bamd\b", re.I),
    "gpu": re.compile(r"näytönohjain|geforce|radeon|\b[RG]TX\b|\bArc\b|gddr|\b\d+ ?GB\b|"
                      r"\bnvidia\b|quadro", re.I),
    "memory": re.compile(r"\bddr\d|dimm|\bram\b|\bCL\d+\b|\d+ ?MHz|MT/s|muistimoduuli", re.I),
    "motherboard": re.compile(r"emolevy|socket|pistoke|\bAM[45]\b|\bLGA\b|\b1[78]\d{2}\b|"
                              r"\b[ABHQXZW]R?X?\d{3}|\b(mini|micro|mikro)[ -]?ITX\b|\bm?ATX\b", re.I),
    "psu": re.compile(r"virtal|netzteil|\bPSU\b|power supply|\d+ ?W(att)?s?\b|80\+", re.I),
    "storage": re.compile(r"\bSSD\b|\bNVMe\b|\bHDD\b|kiintolevy|massamuisti|\bM\.2\b|"
                          # 3+ digit GB only: "12GB" on a storage page is a graphics card's VRAM
                          r"\d+ ?TB\b|\d{3,} ?GB\b|\bSN\d{3,4}\b|\bSATA\b|\bSAS\b", re.I),
    "case": re.compile(r"kotelo|tower|\bcase\b|chassis|\bITX\b|\bATX\b|small form factor|\bSFF\b|"
                       r"tempered glass|\bTG\b", re.I),
}

# Values that only a real component of the category has. Dimensions, colour and voltage
# are not on the list: a floor mat has a width and a fan has a voltage.
DEFINING_FIELDS = {
    "cpu": ("socket", "cores", "threads", "boost_clock_mhz"),
    "gpu": ("vram_gb", "chipset", "graphics_chipset", "gpu_vendor", "memory_type"),
    "memory": ("memory_type", "speed_mhz", "cas_latency"),
    "motherboard": ("socket", "chipset", "memory_type", "memory_slots"),
    "psu": ("wattage_w", "efficiency"),
    "storage": ("kind", "interface", "nvme", "form_factor"),
}


def classify(category: str, raw_name: str) -> Tuple[str, Optional[str]]:
    """("keep", None), ("move", new_category) or ("exclude", "accessory")."""
    if ACCESSORY_PATTERN.search(raw_name):
        return "exclude", "accessory"
    own = OWN_CATEGORY_SIGNAL.get(category)
    if own is None or own.search(raw_name):
        return "keep", None
    for target, pattern in CATEGORY_TYPE_PATTERNS.items():
        if target != category and pattern.search(raw_name):
            return "move", target
    return "keep", None


def lacks_identity(category: str, specs: Optional[Dict[str, Any]], raw_name: str) -> bool:
    """True when nothing known about the row says it is a component of its category.

    Cases are not checked: case names rarely carry any spec, so a real case without a data
    sheet looks exactly like this, and a case that is not checked is shown as "could not
    check" rather than offered as something it is not.
    """
    fields = DEFINING_FIELDS.get(category)
    if not fields:
        return False
    if any((specs or {}).get(field) not in (None, "", []) for field in fields):
        return False
    return not OWN_CATEGORY_SIGNAL[category].search(raw_name or "")
