// MOCK DATA. This is the shape the Express API should return.
// Notes are mock text: the real API should return codes that strings.ts translates.
// Agree on the field names with whoever builds the API, and update this as needed.
// Prices are in cents (same as the database): 19900 = €199.00.

export const GAMES = [
  { id: "cs2", name: "Counter-Strike 2" },
  { id: "fortnite", name: "Fortnite" },
  { id: "valorant", name: "Valorant" },
  { id: "cyberpunk2077", name: "Cyberpunk 2077" },
  { id: "minecraft", name: "Minecraft" },
];

export const mockBuild = {
  budgetCents: 120000,
  game: "cs2",
  totalCents: 122460,
  parts: [
    { category: "cpu", name: "AMD Ryzen 5 7600", priceCents: 19990, shop: "Jimms", url: "#" },
    { category: "cooler", name: "Thermalright Peerless Assassin 120 SE", priceCents: 3990, shop: "Proshop", url: "#" },
    { category: "motherboard", name: "MSI B650 Gaming Plus WiFi", priceCents: 16990, shop: "Datatronic", url: "#" },
    { category: "memory", name: "Kingston Fury Beast 32GB DDR5-6000", priceCents: 10990, shop: "Proshop", url: "#" },
    { category: "gpu", name: "NVIDIA GeForce RTX 5060 Ti 16GB", priceCents: 45990, shop: "Datatronic", url: "#" },
    { category: "storage", name: "WD Black SN770 1TB", priceCents: 6990, shop: "Jimms", url: "#" },
    { category: "psu", name: "Corsair RM750e 750W", priceCents: 9990, shop: "Proshop", url: "#" },
    { category: "case", name: "Fractal Design Pop Air", priceCents: 7530, shop: "Datatronic", url: "#" },
  ],
  fps: [
    { resolution: "1080p", settings: "high", min: 260, max: 340 },
    { resolution: "1440p", settings: "high", min: 190, max: 250 },
    { resolution: "4K", settings: "medium", min: 95, max: 130 },
  ],
  notes: [
    "CS2 on prosessorivetoinen peli, joten Ryzen 5 7600 rajoittaa FPS:ää 1080p:llä.",
    "Arvio perustuu julkisiin benchmarkeihin. Todellinen FPS vaihtelee kartan ja tilanteen mukaan.",
  ],
};
