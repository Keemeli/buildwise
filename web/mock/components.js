// MOCK CATALOG. Approximate prices, for layout and testing only.
// Spec keys match the `specs` JSONB column in the database schema.
// Prices are in cents: 19990 = €199.90.

export const SLOTS = [
  { category: "cpu" },
  { category: "cooler" },
  { category: "motherboard" },
  { category: "memory" },
  { category: "gpu" },
  { category: "storage" },
  { category: "psu" },
  { category: "case" },
];

const offer = (shop, priceCents, inStock = true) => ({ shop, priceCents, inStock, url: "#" });

export const COMPONENTS = [
  // --- CPU ---
  { id: "cpu-7600", category: "cpu", brand: "AMD", model: "Ryzen 5 7600",
    specs: { socket: "AM5", cores: 6, threads: 12, tdp_w: 65, igpu: true, cooler_included: true },
    offers: [offer("Jimms", 19990), offer("Datatronic", 20490), offer("Proshop", 19890)] },
  { id: "cpu-7800x3d", category: "cpu", brand: "AMD", model: "Ryzen 7 7800X3D",
    specs: { socket: "AM5", cores: 8, threads: 16, tdp_w: 120, igpu: true, cooler_included: false },
    offers: [offer("Jimms", 38990), offer("Proshop", 37990)] },
  { id: "cpu-9800x3d", category: "cpu", brand: "AMD", model: "Ryzen 7 9800X3D",
    specs: { socket: "AM5", cores: 8, threads: 16, tdp_w: 120, igpu: true, cooler_included: false },
    offers: [offer("Datatronic", 52990), offer("Proshop", 51990, false)] },
  { id: "cpu-14400f", category: "cpu", brand: "Intel", model: "Core i5-14400F",
    specs: { socket: "LGA1700", cores: 10, threads: 16, tdp_w: 148, igpu: false, cooler_included: true },
    offers: [offer("Jimms", 14990), offer("Datatronic", 15490)] },
  { id: "cpu-12400f", category: "cpu", brand: "Intel", model: "Core i5-12400F",
    specs: { socket: "LGA1700", cores: 6, threads: 12, tdp_w: 117, igpu: false, cooler_included: true },
    offers: [offer("Proshop", 10990)] },

  // --- Cooler ---
  { id: "cool-pa120se", category: "cooler", brand: "Thermalright", model: "Peerless Assassin 120 SE",
    specs: { height_mm: 155, sockets: ["AM5", "LGA1700"], tdp_rating_w: 245 },
    offers: [offer("Proshop", 3990), offer("Jimms", 4290)] },
  { id: "cool-freezer36", category: "cooler", brand: "ARCTIC", model: "Freezer 36",
    specs: { height_mm: 159, sockets: ["AM5", "LGA1700"], tdp_rating_w: 200 },
    offers: [offer("Datatronic", 3490)] },
  { id: "cool-nhd15g2", category: "cooler", brand: "Noctua", model: "NH-D15 G2",
    specs: { height_mm: 168, sockets: ["AM5", "LGA1700"], tdp_rating_w: 250 },
    offers: [offer("Jimms", 14990), offer("Proshop", 14490)] },
  { id: "cool-purerock3", category: "cooler", brand: "be quiet!", model: "Pure Rock 3",
    specs: { height_mm: 155, sockets: ["AM5", "LGA1700"], tdp_rating_w: 150 },
    offers: [offer("Datatronic", 3990)] },

  // --- Motherboard ---
  { id: "mb-b650-gp", category: "motherboard", brand: "MSI", model: "B650 Gaming Plus WiFi",
    specs: { socket: "AM5", chipset: "B650", memory_type: "DDR5", form_factor: "ATX", m2_slots: 2 },
    offers: [offer("Datatronic", 16990), offer("Jimms", 17490)] },
  { id: "mb-b650m-tuf", category: "motherboard", brand: "ASUS", model: "TUF Gaming B650M-E WiFi",
    specs: { socket: "AM5", chipset: "B650", memory_type: "DDR5", form_factor: "mATX", m2_slots: 2 },
    offers: [offer("Proshop", 15990)] },
  { id: "mb-b760m-ddr4", category: "motherboard", brand: "MSI", model: "PRO B760M-A WiFi DDR4",
    specs: { socket: "LGA1700", chipset: "B760", memory_type: "DDR4", form_factor: "mATX", m2_slots: 2 },
    offers: [offer("Jimms", 12990), offer("Datatronic", 13490)] },
  { id: "mb-b760-gx", category: "motherboard", brand: "Gigabyte", model: "B760 Gaming X AX",
    specs: { socket: "LGA1700", chipset: "B760", memory_type: "DDR5", form_factor: "ATX", m2_slots: 3 },
    offers: [offer("Proshop", 15490)] },

  // --- Memory ---
  { id: "ram-fury-32-ddr5", category: "memory", brand: "Kingston", model: "Fury Beast 32GB DDR5-6000",
    specs: { memory_type: "DDR5", capacity_gb: 32, speed_mhz: 6000, modules: 2 },
    offers: [offer("Proshop", 10990), offer("Jimms", 11490)] },
  { id: "ram-veng-32-ddr5", category: "memory", brand: "Corsair", model: "Vengeance 32GB DDR5-6000",
    specs: { memory_type: "DDR5", capacity_gb: 32, speed_mhz: 6000, modules: 2 },
    offers: [offer("Datatronic", 11290)] },
  { id: "ram-fury-16-ddr4", category: "memory", brand: "Kingston", model: "Fury Beast 16GB DDR4-3200",
    specs: { memory_type: "DDR4", capacity_gb: 16, speed_mhz: 3200, modules: 2 },
    offers: [offer("Jimms", 4490)] },

  // --- GPU --- (perf_index: relative gaming performance, used by the mock FPS estimate)
  { id: "gpu-9060xt", category: "gpu", brand: "AMD", model: "Radeon RX 9060 XT 16GB",
    specs: { vram_gb: 16, tdp_w: 160, length_mm: 230, rt_support: true, fg_support: true, perf_index: 0.95 },
    offers: [offer("Datatronic", 39990), offer("Proshop", 38990)] },
  { id: "gpu-5060ti", category: "gpu", brand: "NVIDIA", model: "GeForce RTX 5060 Ti 16GB",
    specs: { vram_gb: 16, tdp_w: 180, length_mm: 250, rt_support: true, fg_support: true, perf_index: 1.0 },
    offers: [offer("Datatronic", 45990), offer("Jimms", 46990)] },
  { id: "gpu-5070", category: "gpu", brand: "NVIDIA", model: "GeForce RTX 5070 12GB",
    specs: { vram_gb: 12, tdp_w: 250, length_mm: 300, rt_support: true, fg_support: true, perf_index: 1.3 },
    offers: [offer("Jimms", 59990), offer("Proshop", 58990)] },
  { id: "gpu-9070xt", category: "gpu", brand: "AMD", model: "Radeon RX 9070 XT 16GB",
    specs: { vram_gb: 16, tdp_w: 304, length_mm: 335, rt_support: true, fg_support: true, perf_index: 1.6 },
    offers: [offer("Datatronic", 72990), offer("Proshop", 71990)] },
  { id: "gpu-5080", category: "gpu", brand: "NVIDIA", model: "GeForce RTX 5080 16GB",
    specs: { vram_gb: 16, tdp_w: 360, length_mm: 340, rt_support: true, fg_support: true, perf_index: 2.0 },
    offers: [offer("Jimms", 124990)] },

  // --- Storage ---
  { id: "ssd-nv3-1tb", category: "storage", brand: "Kingston", model: "NV3 1TB",
    specs: { capacity_gb: 1000, interface: "NVMe PCIe 4.0", form_factor: "M.2 2280" },
    offers: [offer("Jimms", 5490), offer("Proshop", 5290)] },
  { id: "ssd-sn770-1tb", category: "storage", brand: "WD", model: "Black SN770 1TB",
    specs: { capacity_gb: 1000, interface: "NVMe PCIe 4.0", form_factor: "M.2 2280" },
    offers: [offer("Jimms", 6990)] },
  { id: "ssd-990pro-2tb", category: "storage", brand: "Samsung", model: "990 Pro 2TB",
    specs: { capacity_gb: 2000, interface: "NVMe PCIe 4.0", form_factor: "M.2 2280" },
    offers: [offer("Datatronic", 17990), offer("Proshop", 16990)] },

  // --- PSU ---
  { id: "psu-cx550", category: "psu", brand: "Corsair", model: "CX550",
    specs: { wattage_w: 550, efficiency: "80+ Bronze", modular: false, length_mm: 125 },
    offers: [offer("Proshop", 5990)] },
  { id: "psu-pp12-650", category: "psu", brand: "be quiet!", model: "Pure Power 12 650W",
    specs: { wattage_w: 650, efficiency: "80+ Gold", modular: true, length_mm: 160 },
    offers: [offer("Datatronic", 8490), offer("Jimms", 8990)] },
  { id: "psu-rm750e", category: "psu", brand: "Corsair", model: "RM750e",
    specs: { wattage_w: 750, efficiency: "80+ Gold", modular: true, length_mm: 140 },
    offers: [offer("Proshop", 9990), offer("Jimms", 10490)] },
  { id: "psu-rm850x", category: "psu", brand: "Corsair", model: "RM850x",
    specs: { wattage_w: 850, efficiency: "80+ Gold", modular: true, length_mm: 160 },
    offers: [offer("Datatronic", 13990)] },

  // --- Case ---
  { id: "case-popair", category: "case", brand: "Fractal Design", model: "Pop Air",
    specs: { form_factors: ["ATX", "mATX", "ITX"], max_gpu_length_mm: 405, max_cooler_height_mm: 170 },
    offers: [offer("Datatronic", 7530), offer("Proshop", 7990)] },
  { id: "case-4000d", category: "case", brand: "Corsair", model: "4000D Airflow",
    specs: { form_factors: ["ATX", "mATX", "ITX"], max_gpu_length_mm: 360, max_cooler_height_mm: 170 },
    offers: [offer("Jimms", 9990)] },
  { id: "case-a3", category: "case", brand: "Lian Li", model: "A3-mATX",
    specs: { form_factors: ["mATX", "ITX"], max_gpu_length_mm: 415, max_cooler_height_mm: 165 },
    offers: [offer("Proshop", 7490)] },
  { id: "case-nr200p", category: "case", brand: "Cooler Master", model: "NR200P",
    specs: { form_factors: ["ITX"], max_gpu_length_mm: 330, max_cooler_height_mm: 155 },
    offers: [offer("Jimms", 10990)] },
];

// Mock FPS baseline for a perf_index 1.0 GPU (≈ RTX 5060 Ti). Real numbers will come from the engine.
export const FPS_BASELINE = {
  cs2: [
    { resolution: "1080p", settings: "high", min: 260, max: 340 },
    { resolution: "1440p", settings: "high", min: 190, max: 250 },
    { resolution: "4K", settings: "medium", min: 95, max: 130 },
  ],
  fortnite: [
    { resolution: "1080p", settings: "high", min: 140, max: 180 },
    { resolution: "1440p", settings: "high", min: 95, max: 125 },
    { resolution: "4K", settings: "medium", min: 55, max: 70 },
  ],
  valorant: [
    { resolution: "1080p", settings: "high", min: 350, max: 450 },
    { resolution: "1440p", settings: "high", min: 260, max: 330 },
    { resolution: "4K", settings: "high", min: 150, max: 190 },
  ],
  cyberpunk2077: [
    { resolution: "1080p", settings: "high", min: 70, max: 85 },
    { resolution: "1440p", settings: "high", min: 48, max: 58 },
    { resolution: "4K", settings: "medium", min: 26, max: 32 },
  ],
  minecraft: [
    { resolution: "1080p", settings: "high", min: 200, max: 300 },
    { resolution: "1440p", settings: "high", min: 160, max: 230 },
    { resolution: "4K", settings: "high", min: 90, max: 130 },
  ],
};

export function cheapestOffer(component) {
  return component.offers.reduce((best, o) => (o.priceCents < best.priceCents ? o : best));
}

export function findComponent(id) {
  return COMPONENTS.find((c) => c.id === id) ?? null;
}
