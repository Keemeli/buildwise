# Datatronic product identity fixture

Reduced from user-saved browser HTML for the Gigabyte RTX 5070 Ti WindForce OC.
The source manifest records URL, identifiers, saved-file time and hashes; the
saved-file time is not an HTTP fetch timestamp.

The fixture preserves the canonical URL, a real unrelated navigation product ID,
the primary product input, and the primary product details. The data-product JSON
is reduced to its actual id/id_product/reference/link fields. Manufacturer logo
alt text, the displayed Tuotekoodi/sku, and GTIN meta value are retained. Image
URLs, scripts, unrelated product cards and all other page data are omitted.

Here sku means the displayed manufacturer code, not the internal product ID.
No parser selectors or synthetic source values were invented for this fixture.


`product_gpu_166662.html` additionally preserves the primary product's 49
feature name/value pairs in their original order, including package dimensions
before the card dimensions and the vendor family before the processor model.
The rendered product-features section provides the actual definition-list
fallback. Session/tracking fields are excluded from data-product JSON. The
separate source manifest records original/fixture hashes and saved-file time.

For this GPU the published card axes are Pituus 304 mm, Tuotteen korkeus 126 mm
and Tuotteen syvyys 50 mm. The last is card thickness, corresponding to the shared
width_mm convention corroborated by Proshop's saved sheet for the same MPN.
Pakkauksen leveys/syvyys/korkeus 230/398/85 mm are packaging dimensions.
