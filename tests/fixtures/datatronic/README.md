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
