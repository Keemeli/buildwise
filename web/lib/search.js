// Part search by name.
//
// Every word of the query must appear somewhere in the name, in any order, so
// "asus 5070" finds "ASUS GeForce RTX 5070 Prime OC". Case, accents and the
// spaces/dashes inside a model number do not matter either: "5070ti" finds
// "RTX 5070 Ti", and "naytonohjain" finds "näytönohjain".

const fold = (text) =>
  text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

// The name in two forms: words as written, and with the separators removed.
export function searchKey(name) {
  const spaced = fold(name || "");
  return { spaced, compact: spaced.replace(/[\s\-_/]+/g, "") };
}

export function queryTokens(query) {
  return fold(query || "")
    .split(/[\s,]+/)
    .map((token) => token.replace(/[\-_/]+/g, ""))
    .filter(Boolean);
}

export function matchesQuery(key, tokens) {
  return tokens.every((token) => key.spaced.includes(token) || key.compact.includes(token));
}
