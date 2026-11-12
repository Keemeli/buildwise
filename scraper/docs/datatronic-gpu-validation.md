# Datatronic GPU specification validation

Validated offline against the user-saved Gigabyte RTX 5070 Ti WindForce OC page
(retailer ID 166662, manufacturer code GV-N507TWF3OC-16GD). The reduced fixture
and source manifest are in `tests/fixtures/datatronic/product_gpu_166662.*`.
Saved-file time is not a verified HTTP fetch time. This is one real GPU sample,
not a claim that every Datatronic GPU layout has been validated.

## Corrections

The previous substring matching allowed a shorter label to consume a different
field that appeared earlier. GPU labels now require exact case-insensitive
agreement (or an explicit configured regular expression). Other categories retain
their existing matching behaviour.

| Canonical field | Published label | Verified value |
| --- | --- | --- |
| interface | PCI-väylä | PCI Express x16 5.0 |
| memory_bus_bit | Muistiväylä | 256 |
| graphics_chipset | Grafiikkaprosessori | GeForce RTX 5070 Ti |
| length_mm | Pituus | 304 |
| width_mm | Tuotteen syvyys | 50 |
| height_mm | Tuotteen korkeus | 126 |
| power_w | Thermal Design Power (TDP) | 300 |
| recommended_psu_w | Virtalähteen minimikoko | 750 |
| power_connectors | Lisävirran liittimet | 1x 16-pin |
| slot_width | Laajennuspaikkoja | 2 |

`Grafiikkaprosessorin perhe = NVIDIA` is a vendor-family label; it cannot populate
the processor model. The catalogue already keeps vendor separately through its
existing name parser. No new specification schema fields are introduced.

For this card the primary published depth is thickness, corresponding to the
shared width convention confirmed by Proshop's saved sheet for the same MPN.
Pakkauksen leveys/syvyys/korkeus = 230/398/85 mm describe the package and never
supply card dimensions. If multiple supported card-axis aliases disagree, that
canonical field remains unknown. Axis order is not guessed from composite sizes;
dimensions require one explicit positive measurement with a unit. Physical
thickness (`Paksuus`) is not interpreted as a number of occupied slots.

Features come from the primary `#product-details` JSON, falling back to its
rendered definition list. Unrelated page scripts and definition lists cannot
replace the primary product's fields. Historical snippets without the primary
container retain standalone JSON-script and definition-list compatibility.
Conflicting GPU aliases remain unknown and are reported instead of taking the
first value. Equivalent measurements, such as 30.4 cm and 304 mm, agree.

## Offline integration result

The isolated five-listing sample uses saved Datatronic, Jimms and Proshop
responses. It produces three components:

- One verified group containing all three offers for GV-N507TWF3OC-16GD, with
  GTIN 04719331355579. Each shop retains its price, URL and numeric retailer ID.
- One separate Jimms RTX 5070 12 GB with different GTIN/MPN.
- One separate Proshop V2 listing without cached product identity. Its offline
  specification request reports a cache miss and returns nonzero as expected;
  successful product extraction remains available, with no network fallback.

The merged card dimensions are 304/50/126 mm; the package-dimension conflicts are
resolved. Chipset, interface and connector wording still differs between shops.
At the end of this parser milestone those merged fields remained null, with their
original values in `spec_conflicts`; retailer-specific values stayed in `specs.json`.
The subsequent [GPU vocabulary policy](gpu-specification-values.md) resolves only
recognised wording differences, with originals retained in `spec_observations`.

These prices come from historical observations, not current offers. The isolated
sample supplies the numeric IDs visible in saved Jimms URLs where legacy raw
observations had null IDs. It does not migrate the real raw files.

Verification uses the existing shared CLI and temporary output with HTTP requests
mocked to fail if attempted. It updates neither the existing specification store
nor the deployed catalogue. Focused regression cases cover source scoping,
package exclusion, alias conflicts, units and parser injection.
