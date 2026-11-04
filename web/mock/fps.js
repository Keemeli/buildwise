// MOCK FPS DATA. Placeholder until the engine has a real performance model.
//
// FPS_BASELINE is for a GPU with perf index 1.0 (≈ RTX 5060 Ti 16GB).
// PERF_BY_CHIPSET is a rough relative gaming performance per GPU chip.
// Keys use chipsetKey() from lib/catalog.js: uppercase, no spaces.

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

export const PERF_BY_CHIPSET = {
  RTX3050: 0.45,
  RX7600: 0.7,
  ARCB580: 0.8,
  RTX5060: 0.85,
  RTX5060TI: 1.0,
  RX9060XT: 0.95,
  RTX5070: 1.3,
  RX9070GRE: 1.3,
  RX9070: 1.45,
  RX9070XT: 1.6,
  RTX5070TI: 1.6,
  RTX5080: 2.0,
};
