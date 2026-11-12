# Compatibility rules

What the build checker decides, which field it reads for each decision, and what it
refuses to decide. Written for the team, for the demo video, and for whoever moves these
rules into the Express engine later — the rules and the honesty rules travel together.

Implementation: `web/lib/compat.js`. Messages: `web/strings.ts` (`fi` / `en`).
The behaviour is checked on every pull request by `web/scripts/check-data-contract.mjs`.

## The three outcomes

| Level | Meaning |
|---|---|
| `error` | The parts do not work together. |
| `warning` | It works, but something needs attention. |
| `unknown` | The check could not run, because the data is missing the field it needs. |

**Never report `ok` for a check we could not run.** A build of two parts must not show a
clean panel: `checkCoverage()` counts the areas that could actually run and the panel
says, in words, how many of the 8 areas were checked and which parts are still waiting.

## Field contract

The rules compare values, so both sides must use one vocabulary and one shape. That is
enforced in the pipeline, not in the rules.

| Field | Read by | Canonical form |
|---|---|---|
| `cpu.socket`, `motherboard.socket` | socket rule | `AM5`, `AM4`, `LGA1700`, `LGA1851`, `sTR5` — from the data sheet, or inferred from the chipset and marked as inferred |
| `memory.memory_type`, `motherboard.memory_type` | memory rule | DDR generation only: `DDR4`, `DDR5`. A board that supports two generations keeps a list. |
| `cooler.sockets` | cooler mount rule | list of socket names |
| `cooler.height_mm`, `case.max_cooler_height_mm` | cooler height rule | millimetres, number |
| `gpu.length_mm`, `case.max_gpu_length_mm` | GPU length rule | millimetres, number |
| `motherboard.form_factor`, `case.form_factors` | form factor rule | the app maps `Micro-ATX` → `mATX`, `Mini-ITX` → `ITX` before comparing |
| `memory.form_factor` | laptop memory rule | `SO-DIMM` means laptop memory |
| `gpu.recommended_psu_w` | PSU rule | the manufacturer's **minimum PSU size for the whole system** |
| `cpu.tdp_w`, `gpu.power_w` | power estimate | watts, number |
| `psu.wattage_w` | PSU rule | watts, number |
| `cpu.cooler_included` | cooler warning | only an explicit `false` warns; `null` means "not known" |
| `cpu.igpu` / `cpu.integrated_graphics` | GPU warning | same rule |

**Why the vocabulary is a rule, not a detail:** a DDR4 kit and a DDR4 board were once
reported as incompatible, because the board's data sheet said `DDR4-SDRAM` and the
memory's product name said `DDR4`. The pipeline now canonicalises
(`parse_memory_type()` in `scraper/specs.py`), the engine keeps a comparison safety net
(`ddrGenerations()`), the normalisation report prints the facet vocabulary on every run,
and CI runs a contract check. Same treatment for storage (`SATA III`, `M.2 2280`).

## The rules

| Code | Parts | Condition | Level |
|---|---|---|---|
| `socketMismatch` | cpu, motherboard | sockets differ | error |
| `socketUnknown` | cpu, motherboard | either socket is missing | unknown |
| `memoryMismatch` | memory, motherboard | no shared DDR generation | error |
| `memoryUnknown` | memory, motherboard | either memory type is missing | unknown |
| `laptopMemory` | memory | `form_factor == "SO-DIMM"` (laptop memory in a desktop build) | error |
| `coolerSocket` | cooler, cpu | the cooler's socket list does not include the CPU socket | error |
| `coolerSocketUnknown` | cooler, cpu | socket list or CPU socket missing | unknown |
| `formFactor` | motherboard, case | the case does not list the board's form factor | error |
| `formFactorUnknown` | motherboard, case | either list missing | unknown |
| `gpuLength` | gpu, case | `length_mm > max_gpu_length_mm` | error |
| `gpuLengthUnknown` | gpu, case | either number missing | unknown |
| `coolerHeight` | cooler, case | `height_mm > max_cooler_height_mm` | error |
| `coolerHeightUnknown` | cooler, case | either number missing | unknown |
| `psuTooWeak` | psu | wattage below the estimated draw | error |
| `psuLowHeadroom` | psu | wattage below 1.3 × the estimated draw (advice, not a verdict) | warning |
| `psuBelowMinimum` | psu | wattage below the GPU manufacturer's minimum | error |
| `powerUnknown` | psu | neither a power figure nor a manufacturer minimum is in the data | unknown |
| `needsCooler` | cpu, cooler | no cooler chosen and the CPU ships without one | warning |
| `needsGpu` | cpu, gpu | no GPU chosen and the CPU has no integrated graphics | warning |

`issuesForCandidate(build, candidate)` answers "would this part break the build?" and is
what the picker uses to mark a part before you add it.

## Power estimation

`powerBasis()` returns what a number is based on, and the panel says it out loud:

| Basis | Meaning |
|---|---|
| `parts` | summed from the chosen parts' own figures: `(cpu.tdp_w ?? power_w) + (gpu.tdp_w ?? power_w) + 75 W` |
| `manufacturerMin` | the GPU data sheet's minimum PSU size for the whole system |
| `none` | no CPU or GPU chosen yet |
| `unknown` | neither figure exists in the data |

The 75 W covers motherboard, memory, storage and fans. `estimateWattage()` is an
estimate and is labelled as one — it is not a measurement.

Two PSU branches, deliberately different:

* **Parts basis** — the sum is a rough draw, so spare capacity matters: below 1.3 × the
  estimate you get `psuLowHeadroom` with a recommendation rounded up to the next 50 W.
* **Manufacturer minimum** — this figure already includes the manufacturer's own
  allowance for the rest of the system, so it is checked directly. Demanding 30 % on top
  would push people to oversized units. It is never shown as a power draw, only as a
  minimum PSU size.

## What the engine deliberately does not claim

* **Frames per second.** The estimator is modelled from a chipset index and per-game
  resolution scaling, with confidence tiers; it is not measured data and is not presented
  as such.
* **Physical fit beyond two numbers.** GPU length and cooler height only. Radiator
  thickness, GPU slot thickness and width, motherboard standoff positions, cable bend
  radius and case fan counts are not modelled.
* **Electrical detail.** PSU connector counts, transient spikes, cable gauge.
* **Firmware and revisions.** BIOS version support per CPU, CPU cooler mounting kits,
  early-batch issues.
* **Memory beyond generation.** Rank, timings, XMP/EXPO stability, four-stick speeds.

If a rule needs one of these, it needs a new field in the pipeline first — and until that
field exists, the honest answer for that check is `unknown`, not silence.

## Adding or changing a rule

1. Implement it in `web/lib/compat.js` (keep it in sync with the future Express engine).
2. Add both language strings in `web/strings.ts` under `issues`.
3. Add a case to `web/scripts/check-data-contract.mjs` — that runs in CI on every PR.
   Include the inverse case: a genuine mismatch must still be an error.
4. If the rule adds a panel area, add it to `CHECK_AREAS`.
5. If the rule needs a new field: `scraper/specs.py` (FIELD_MAP + parser),
   `scraper/normalise.py` (merge + report), then `web/components/PartPicker.js` to show it.
6. Update this document.

## Verified examples (real catalogue rows)

| Build | Result |
|---|---|
| 9800X3D (120 W) + RTX 5060 Ti (180 W) | 375 W estimated, basis `parts` |
| 9800X3D (120 W) + RTX 5070 (250 W) | 445 W estimated — the figure shown on the deployed site |
| RX 9070 XT (manufacturer min 850 W) + 400 W PSU | `psuBelowMinimum` — and no headroom warning on that path |
| DDR5 kit + B550 board | `memoryMismatch` |
| DDR4 kit + B550 board | clean — this is the case the vocabulary bug broke |
| Memory + motherboard only | panel: "2/8 checks ran, no problems. Waiting for: CPU, cooler, case, GPU, PSU" |
