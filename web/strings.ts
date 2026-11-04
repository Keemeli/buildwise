// All UI text lives here. Components never contain hard-coded strings.
// Product names are NEVER translated: they are shown exactly as the shop writes them.
// Spec values (socket, VRAM, wattage, form factor) are normalised and language-neutral.

type Params = Record<string, string | number>;

// "Emolevy" -> "emolevy", but "CPU-jäähdytin" stays as is.
const lowerFirst = (s: string) => (/^\p{Lu}\p{Ll}/u.test(s) ? s[0].toLowerCase() + s.slice(1) : s);

export const strings = {
  fi: {
    locale: "fi-FI",

    meta: {
      title: "BuildWise",
      description: "PC-kokoonpanot suomalaisten kauppojen hinnoilla ja rehellisellä FPS-arviolla",
    },
    footer: (shops: string, date: string) => `Hinnat: ${shops}. Päivitetty ${date}.`,

    categories: {
      cpu: "Prosessori",
      cooler: "CPU-jäähdytin",
      motherboard: "Emolevy",
      memory: "Muisti",
      gpu: "Näytönohjain",
      storage: "Tallennustila",
      psu: "Virtalähde",
      case: "Kotelo",
    },

    builder: {
      title: "Kokoonpanosi",
      clearAll: "Tyhjennä",
      choose: (category: string) => `+ Valitse ${lowerFirst(category)}`,
      change: "Vaihda",
      remove: (category: string) => `Poista ${lowerFirst(category)}`,
      total: "Yhteensä",
      powerDraw: "Arvioitu virrankulutus",
      partsChosen: "Osia valittu",
      compatibility: "Yhteensopivuus",
      addPartsToCheck: "Lisää osia, niin tarkistamme yhteensopivuuden.",
      noProblems: "✓ Ei ongelmia.",
      checkedOk: "✓ Tarkistetuissa kohdissa ei ongelmia.",
      fpsTitle: "FPS-arvio",
      fpsMockNote: "Valedataan perustuva arvio, joka huomioi vain näytönohjaimen.",
      chooseGpuForFps: "Valitse näytönohjain, niin näet arvion.",
      budgetCard: "Et tiedä mistä aloittaa? Valitse osat budjetin mukaan",
    },

    picker: {
      title: (category: string) => `Valitse ${lowerFirst(category)}`,
      searchPlaceholder: "Hae nimellä…",
      close: "Sulje",
      add: "Lisää",
      shops: (n: number) => `${n} kauppaa`,
      noMatches: (query: string) => `Haulla ”${query}” ei löytynyt osia.`,
      emptyCategory: "Tämän kategorian osia ei ole vielä haettu kaupoista.",
    },

    specs: {
      coresThreads: (cores: number, threads: number) => `${cores} ydintä / ${threads} säiettä`,
      coolerIncluded: "jäähdytin mukana",
      height: (mm: number) => `${mm} mm korkea`,
      upToWatts: (w: number) => `enintään ${w} W`,
      vram: (gb: number) => `${gb} GB VRAM`,
      modular: "modulaarinen",
      gpuUpTo: (mm: number) => `näytönohjain enintään ${mm} mm`,
      coolerUpTo: (mm: number) => `jäähdytin enintään ${mm} mm`,
      clock: (ghz: number) => `${ghz.toLocaleString("fi-FI")} GHz`,
      cache: (mb: number) => `${mb} MB välimuisti`,
      colors: { black: "musta", white: "valkoinen", grey: "harmaa", wood: "puu" } as Record<string, string>,
    },

    preview: {
      label: "Kuva kokoonpanosta kotelon sivuikkunan läpi",
      rear: "Takaosa",
      front: "Etuosa",
      cpu: "CPU",
      cooler: "Jäähdytin",
      storage: "SSD",
      psu: "PSU",
    },

    budget: {
      budget: "Budjetti",
      game: "Peli",
      submit: "Hae kokoonpano",
      searchPlaceholder: "Esim. 1200 € pelikone CS2:lle",
    },

    result: {
      changeSearch: "← Muuta hakua",
      loading: "Lasketaan kokoonpanoa…",
      totalPrice: "Kokonaishinta",
      leftInBudget: "Budjettia jää",
      fps1080: "FPS, 1080p",
      components: "Komponentit",
      fpsEstimate: "FPS-arvio",
      table: { part: "Osa", product: "Tuote", shop: "Kauppa", price: "Hinta" },
    },

    fps: {
      estimate: "Arvio",
      noEstimate: "Tälle näytönohjaimelle ei ole vielä arviota.",
      settings: { low: "Matala", medium: "Keskitaso", high: "Korkea", ultra: "Ultra" },
    },

    // Compatibility issues. The engine returns a code + params, the UI turns them into text.
    issues: {
      socketMismatch: (p: Params) => `Prosessorin kanta ${p.cpuSocket} ei sovi ${p.boardSocket}-emolevyyn.`,
      memoryMismatch: (p: Params) => `${p.memoryType}-muisti ei sovi ${p.boardType}-emolevyyn.`,
      coolerSocket: (p: Params) => `Jäähdytin ei tue ${p.socket}-kantaa.`,
      formFactor: (p: Params) => `${p.formFactor}-emolevy ei mahdu tähän koteloon.`,
      gpuLength: (p: Params) => `Näytönohjain on ${p.length} mm pitkä, koteloon mahtuu ${p.max} mm.`,
      coolerHeight: (p: Params) => `Jäähdytin on ${p.height} mm korkea, koteloon mahtuu ${p.max} mm.`,
      psuTooWeak: (p: Params) => `Virtalähde (${p.psu} W) on heikompi kuin arvioitu kulutus ${p.draw} W.`,
      psuLowHeadroom: (p: Params) =>
        `Virtalähteessä on vähän varaa: ${p.psu} W, kun kulutus on noin ${p.draw} W. Suositus ${p.recommended} W.`,
      psuBelowMinimum: (p: Params) =>
        `Virtalähde (${p.psu} W) on pienempi kuin näytönohjaimen valmistajan vähimmäissuositus ${p.minimum} W.`,
      needsCooler: () => "Tämän prosessorin mukana ei tule jäähdytintä. Lisää jäähdytin.",
      needsGpu: () => "Tässä prosessorissa ei ole integroitua grafiikkaa. Lisää näytönohjain.",
      laptopMemory: () => "Tämä on kannettavan tietokoneen muisti (SO-DIMM), eikä se sovi pöytäkoneen emolevyyn.",
      socketUnknown: () => "Prosessorin ja emolevyn kantaa ei voitu verrata, koska tieto puuttuu.",
      memoryUnknown: () => "Muistin ja emolevyn muistityyppiä ei voitu verrata, koska tieto puuttuu.",
      coolerSocketUnknown: () => "Jäähdyttimen kantatukea ei voitu tarkistaa.",
      formFactorUnknown: () => "Emolevyn mahtumista koteloon ei voitu tarkistaa, koska kotelon tukemat emolevykoot puuttuvat.",
      gpuLengthUnknown: () => "Näytönohjaimen mahtumista koteloon ei voitu tarkistaa, koska mitat puuttuvat.",
      coolerHeightUnknown: () => "Jäähdyttimen mahtumista koteloon ei voitu tarkistaa, koska mitat puuttuvat.",
      powerUnknown: () => "Virtalähteen riittävyyttä ei voitu tarkistaa, koska osien virrankulutus puuttuu.",
    },
  },

  en: {
    locale: "en-IE",

    meta: {
      title: "BuildWise",
      description: "PC builds with Finnish retailer prices and an honest FPS estimate",
    },
    footer: (shops: string, date: string) => `Prices from ${shops}. Updated ${date}.`,

    categories: {
      cpu: "Processor",
      cooler: "CPU cooler",
      motherboard: "Motherboard",
      memory: "Memory",
      gpu: "Graphics card",
      storage: "Storage",
      psu: "Power supply",
      case: "Case",
    },

    builder: {
      title: "Your build",
      clearAll: "Clear all",
      choose: (category: string) => `+ Choose ${lowerFirst(category)}`,
      change: "Change",
      remove: (category: string) => `Remove ${lowerFirst(category)}`,
      total: "Total",
      powerDraw: "Estimated power draw",
      partsChosen: "Parts chosen",
      compatibility: "Compatibility",
      addPartsToCheck: "Add parts to check compatibility.",
      noProblems: "✓ No problems found.",
      checkedOk: "✓ No problems in the checks we could run.",
      fpsTitle: "FPS estimate",
      fpsMockNote: "Mock estimate based on the graphics card only.",
      chooseGpuForFps: "Choose a graphics card to see an estimate.",
      budgetCard: "Not sure where to start? Pick parts for my budget",
    },

    picker: {
      title: (category: string) => `Choose ${lowerFirst(category)}`,
      searchPlaceholder: "Search by name…",
      close: "Close",
      add: "Add",
      shops: (n: number) => `${n} shops`,
      noMatches: (query: string) => `No parts match “${query}”.`,
      emptyCategory: "Parts in this category have not been scraped yet.",
    },

    specs: {
      coresThreads: (cores: number, threads: number) => `${cores} cores / ${threads} threads`,
      coolerIncluded: "cooler included",
      height: (mm: number) => `${mm} mm tall`,
      upToWatts: (w: number) => `up to ${w} W`,
      vram: (gb: number) => `${gb} GB VRAM`,
      modular: "modular",
      gpuUpTo: (mm: number) => `GPU up to ${mm} mm`,
      coolerUpTo: (mm: number) => `cooler up to ${mm} mm`,
      clock: (ghz: number) => `${ghz.toLocaleString("en-IE")} GHz`,
      cache: (mb: number) => `${mb} MB cache`,
      colors: { black: "black", white: "white", grey: "grey", wood: "wood" } as Record<string, string>,
    },

    preview: {
      label: "Picture of the build through the case side window",
      rear: "Rear",
      front: "Front",
      cpu: "CPU",
      cooler: "Cooler",
      storage: "SSD",
      psu: "PSU",
    },

    budget: {
      budget: "Budget",
      game: "Game",
      submit: "Find my build",
      searchPlaceholder: "e.g. €1200 gaming PC for CS2",
    },

    result: {
      changeSearch: "← Change search",
      loading: "Putting your build together…",
      totalPrice: "Total price",
      leftInBudget: "Left in budget",
      fps1080: "FPS, 1080p",
      components: "Components",
      fpsEstimate: "FPS estimate",
      table: { part: "Part", product: "Product", shop: "Shop", price: "Price" },
    },

    fps: {
      estimate: "Estimate",
      noEstimate: "No estimate for this graphics card yet.",
      settings: { low: "Low", medium: "Medium", high: "High", ultra: "Ultra" },
    },

    issues: {
      socketMismatch: (p: Params) => `CPU socket ${p.cpuSocket} does not fit a ${p.boardSocket} motherboard.`,
      memoryMismatch: (p: Params) => `${p.memoryType} memory does not fit a ${p.boardType} motherboard.`,
      coolerSocket: (p: Params) => `Cooler does not support the ${p.socket} socket.`,
      formFactor: (p: Params) => `An ${p.formFactor} motherboard does not fit this case.`,
      gpuLength: (p: Params) => `Graphics card is ${p.length} mm long, the case fits ${p.max} mm.`,
      coolerHeight: (p: Params) => `Cooler is ${p.height} mm tall, the case fits ${p.max} mm.`,
      psuTooWeak: (p: Params) => `Power supply (${p.psu} W) is below the estimated draw of ${p.draw} W.`,
      psuLowHeadroom: (p: Params) =>
        `Power supply has little headroom: ${p.psu} W for ~${p.draw} W. Aim for ${p.recommended} W.`,
      psuBelowMinimum: (p: Params) =>
        `Power supply (${p.psu} W) is below the minimum the graphics card manufacturer specifies (${p.minimum} W).`,
      needsCooler: () => "This CPU is sold without a cooler. Add one.",
      needsGpu: () => "This CPU has no integrated graphics. Add a graphics card.",
      laptopMemory: () => "This is laptop memory (SO-DIMM) and does not fit a desktop motherboard.",
      socketUnknown: () => "Could not compare CPU and motherboard sockets: data is missing.",
      memoryUnknown: () => "Could not compare memory types: data is missing.",
      coolerSocketUnknown: () => "Could not check the cooler's socket support.",
      formFactorUnknown: () => "Could not check if the motherboard fits the case: supported board sizes are missing.",
      gpuLengthUnknown: () => "Could not check if the graphics card fits the case: dimensions are missing.",
      coolerHeightUnknown: () => "Could not check if the cooler fits the case: dimensions are missing.",
      powerUnknown: () => "Could not check the power supply: power draw of the parts is missing.",
    },
  },
} as const;

export type Locale = keyof typeof strings;

// Default language. Changing this one line switches the whole UI.
export const LOCALE: Locale = "fi";

export const t = strings[LOCALE];
