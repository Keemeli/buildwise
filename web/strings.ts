// All UI text lives here. Components never contain hard-coded strings.
// Product names are NEVER translated: they are shown exactly as the shop writes them.
// Spec values (socket, VRAM, wattage, form factor) are normalised and language-neutral.

type Params = Record<string, string | number>;

// "Emolevy" -> "emolevy", but "CPU-jäähdytin" stays as is.
const lowerFirst = (s: string) => (/^\p{Lu}\p{Ll}/u.test(s) ? s[0].toLowerCase() + s.slice(1) : s);

// Names of the compatibility check areas (lib/compat.js → CHECK_AREAS), for messages
// that list which checks could not run.
const FI_CHECKS: Record<string, string> = {
  cpuSocket: "prosessorin ja emolevyn kanta",
  memoryType: "muistin ja emolevyn muistityyppi",
  memoryForm: "onko muisti pöytäkoneeseen",
  coolerMount: "jäähdyttimen sopivuus kantaan",
  coolerHeight: "jäähdyttimen mahtuminen koteloon",
  formFactor: "emolevyn mahtuminen koteloon",
  gpuLength: "näytönohjaimen mahtuminen koteloon",
  psuPower: "virtalähteen riittävyys",
  cpuExtras: "tarvitaanko erillinen jäähdytin tai näytönohjain",
};
const EN_CHECKS: Record<string, string> = {
  cpuSocket: "CPU and motherboard socket",
  memoryType: "memory type",
  memoryForm: "whether the memory is for desktops",
  coolerMount: "cooler fitting the CPU socket",
  coolerHeight: "whether the cooler fits the case",
  formFactor: "whether the motherboard fits the case",
  gpuLength: "whether the graphics card fits the case",
  psuPower: "whether the power supply is enough",
  cpuExtras: "whether a separate cooler or graphics card is needed",
};
// Finnish genitive of each part ("kotelon mallia ei tiedetä")
const FI_GENITIVE: Record<string, string> = {
  cpu: "prosessorin",
  cooler: "jäähdyttimen",
  motherboard: "emolevyn",
  memory: "muistin",
  gpu: "näytönohjaimen",
  storage: "tallennustilan",
  psu: "virtalähteen",
  case: "kotelon",
};
const EN_PART: Record<string, string> = {
  cpu: "processor",
  cooler: "CPU cooler",
  motherboard: "motherboard",
  memory: "memory",
  gpu: "graphics card",
  storage: "storage",
  psu: "power supply",
  case: "case",
};
type OwnedParams = { category: string; checks: string[] };

export const strings = {
  fi: {
    locale: "fi-FI",

    languageName: "Suomi",
    switchLanguage: "Kieli",
    nav: { builder: "Kokoaja" },
    landing: {
      title: "Pelikone budjettiisi suomalaisilla hinnoilla",
      lead: "Kerro budjetti ja peli. Saat yhteensopivan kokoonpanon kauppojen ajantasaisilla hinnoilla ja rehellisen FPS-arvion.",
      budgetTitle: "Hae budjetilla",
      builderPrompt: "Haluatko valita osat itse?",
      openBuilder: "Avaa kokoaja →",
      upgradeNote: "Päivitätkö vanhaa konetta? Merkitse kokoajassa omat osasi, niin niitä ei lasketa hintaan.",
      compatTitle: "Yhteensopivuus",
      compatText: "Kanta, muisti, mitat ja virta. Kerromme myös, mitä ei voitu tarkistaa.",
      fpsTitle: "Rehellinen FPS",
      fpsText: "Arvio vaihteluvälinä, ei yhtenä lupauksena.",
      catalogTitle: (n: number) => `${n.toLocaleString("fi-FI")} osaa`,
      catalogText: (shops: string, date: string) => `${shops} · päivitetty ${date}`,
      example: "esimerkki",
      moreParts: (n: number) => `+ ${n} muuta osaa`,
      allFit: "Kaikki osat sopivat yhteen",
    },
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
      // "I already have this part" (owned parts are not counted in the price or the budget)
      ownedBadge: "Oma osa",
      ownedNoModel: "Oma osa, malli ei tiedossa",
      ownedNoModelHint: "Valitse malli, jos haluat, että tarkistamme yhteensopivuuden.",
      chooseModel: "Valitse malli",
      notOwned: "ostan uuden",
      ownedParts: "Omat osat (ei hintaan)",
      budgetOwnedNote: (parts: string[]) => `Budjetti käytetään muihin osiin. Omat osat: ${parts.map(lowerFirst).join(", ")}.`,
      compatibility: "Yhteensopivuus",
      addPartsToCheck: "Lisää osia, niin tarkistamme yhteensopivuuden.",
      checksSummary: (p: Params) => `✓ ${p.done}/${p.total} tarkistusta tehtiin, ei ongelmia.`,
      checksNone: "Yhtään tarkistusta ei voitu vielä tehdä.",
      checksWaiting: (p: Params) => `Odottaa osia: ${p.parts}.`,
      powerFromParts: "Laskettu valittujen osien tehonkulutuksesta.",
      powerFromMinimum: "Näytönohjaimen valmistajan vähimmäissuositus koko kokoonpanolle.",
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
      // Spec filters (issue #25)
      facets: {
        socket: "Kanta",
        memoryType: "Muistityyppi",
        formFactor: "Koko",
        vendor: "Valmistaja",
        interface: "Liitäntä",
        wattage: "Teho",
        caseSize: "Kotelon koko",
      } as Record<string, string>,
      unknown: "Ei tiedossa",
      wattage: {
        "w-lt600": "alle 600 W",
        "w-600-749": "600–749 W",
        "w-750-999": "750–999 W",
        "w-gte1000": "1000 W tai yli",
      } as Record<string, string>,
      filters: "Suodattimet",
      clearFilters: "Tyhjennä suodattimet",
      resultCount: (shown: number, total: number) => `${shown} / ${total} osaa`,
      compatibleOnly: (hidden: number) =>
        `Näytetään vain kokoonpanoon sopivat osat. ${hidden} ${hidden === 1 ? "osa" : "osaa"} piilotettu.`,
      showAll: "Näytä kaikki",
      showingAll: "Näytetään myös osat, jotka eivät sovi kokoonpanoon.",
      showCompatibleOnly: "Näytä vain yhteensopivat",
      noFilterMatches: "Valituilla suodattimilla ei löytynyt osia.",
      // "I already have this part"
      haveIt: (category: string) => `Minulla on jo ${lowerFirst(category)}`,
      haveItHint: "ei lasketa hintaan eikä budjettiin",
      haveItHelp: "Valitse oma mallisi listasta, niin tarkistamme yhteensopivuuden.",
      noModel: "En tiedä mallia",
      addOwned: "Minun",
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
      owned: "katkoviiva = oma osa",
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
      ownedParts: (parts: string[]) => `Omat osat, ei budjetissa: ${parts.map(lowerFirst).join(", ")}.`,
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
      ownedModelUnknown: (p: OwnedParams) =>
        `Ei voida tarkistaa, koska oman ${FI_GENITIVE[p.category] ?? p.category} mallia ei tiedetä: ${p.checks
          .map((c) => FI_CHECKS[c] ?? c)
          .join(", ")}. Valitse malli, niin tarkistamme.`,
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

    languageName: "English",
    switchLanguage: "Language",
    nav: { builder: "Builder" },
    landing: {
      title: "A gaming PC for your budget, at Finnish prices",
      lead: "Tell us your budget and the game you play. You get a compatible build with up-to-date prices from Finnish shops and an honest FPS estimate.",
      budgetTitle: "Search by budget",
      builderPrompt: "Rather pick the parts yourself?",
      openBuilder: "Open the builder →",
      upgradeNote: "Upgrading an old PC? Mark the parts you already have in the builder and they're left out of the price.",
      compatTitle: "Compatibility",
      compatText: "Socket, memory, dimensions and power. We also tell you what we couldn't check.",
      fpsTitle: "Honest FPS",
      fpsText: "An estimate as a range, not a single promise.",
      catalogTitle: (n: number) => `${n.toLocaleString("en-IE")} parts`,
      catalogText: (shops: string, date: string) => `${shops} · updated ${date}`,
      example: "example",
      moreParts: (n: number) => `+ ${n} more parts`,
      allFit: "All parts fit together",
    },
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
      // "I already have this part" (owned parts are not counted in the price or the budget)
      ownedBadge: "Your part",
      ownedNoModel: "Your part, model not known",
      ownedNoModelHint: "Choose the model if you want us to check compatibility.",
      chooseModel: "Choose model",
      notOwned: "buy new",
      ownedParts: "Your own parts (not in price)",
      budgetOwnedNote: (parts: string[]) => `The budget goes to the other parts. Your own parts: ${parts.map(lowerFirst).join(", ")}.`,
      compatibility: "Compatibility",
      addPartsToCheck: "Add parts to check compatibility.",
      checksSummary: (p: Params) => `✓ ${p.done}/${p.total} checks ran, no problems found.`,
      checksNone: "No check could run yet.",
      checksWaiting: (p: Params) => `Waiting for parts: ${p.parts}.`,
      powerFromParts: "Summed from the chosen parts' power figures.",
      powerFromMinimum: "The graphics card manufacturer's minimum for the whole build.",
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
      // Spec filters (issue #25)
      facets: {
        socket: "Socket",
        memoryType: "Memory type",
        formFactor: "Size",
        vendor: "Vendor",
        interface: "Interface",
        wattage: "Wattage",
        caseSize: "Case size",
      } as Record<string, string>,
      unknown: "Not known",
      wattage: {
        "w-lt600": "under 600 W",
        "w-600-749": "600–749 W",
        "w-750-999": "750–999 W",
        "w-gte1000": "1000 W or more",
      } as Record<string, string>,
      filters: "Filters",
      clearFilters: "Clear filters",
      resultCount: (shown: number, total: number) => `${shown} / ${total} parts`,
      compatibleOnly: (hidden: number) =>
        `Showing only parts that fit this build. ${hidden} ${hidden === 1 ? "part" : "parts"} hidden.`,
      showAll: "Show all",
      showingAll: "Also showing parts that don't fit this build.",
      showCompatibleOnly: "Show compatible only",
      noFilterMatches: "No parts match the selected filters.",
      // "I already have this part"
      haveIt: (category: string) => `I already have my own ${lowerFirst(category)}`,
      haveItHint: "not counted in the price or the budget",
      haveItHelp: "Pick your model from the list so we can check compatibility.",
      noModel: "I don't know the model",
      addOwned: "Mine",
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
      owned: "dashed = your own part",
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
      ownedParts: (parts: string[]) => `Your own parts, not in the budget: ${parts.map(lowerFirst).join(", ")}.`,
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
      ownedModelUnknown: (p: OwnedParams) =>
        `Can't check ${p.checks.map((c) => EN_CHECKS[c] ?? c).join(", ")}: the model of your own ${
          EN_PART[p.category] ?? p.category
        } isn't known. Choose the model to check it.`,
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

// Default language: what the server renders and what a first-time visitor sees.
// The user can switch language in the header (lib/locale.js remembers the choice).
export const DEFAULT_LOCALE: Locale = "fi";

// Default-language texts for server-only code. Components use `useT()` from lib/locale.js.
export const t = strings[DEFAULT_LOCALE];
