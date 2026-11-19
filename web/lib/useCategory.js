"use client";

import { useEffect, useState } from "react";

// Parts of one category, fetched from /catalog/<category> the first time a picker for it
// opens and kept for the rest of the visit. Component objects are identical to the ones
// lib/catalog.js builds on the server (same ids).

const loaded = new Map(); // category -> parts[]
const pending = new Map(); // category -> Promise<parts[]>

function load(category) {
  if (!pending.has(category)) {
    const request = fetch(`/catalog/${encodeURIComponent(category)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`catalog ${category}: HTTP ${res.status}`);
        return res.json();
      })
      .then((parts) => {
        loaded.set(category, parts);
        return parts;
      })
      .finally(() => pending.delete(category)); // a failed load is tried again next time
    pending.set(category, request);
  }
  return pending.get(category);
}

// { parts: parts[] | null, loading: boolean, error: Error | null }
export function useCategory(category) {
  const [failed, setFailed] = useState(null); // { category, error }
  const [, setDone] = useState(0); // re-render once the fetch has filled `loaded`

  useEffect(() => {
    if (loaded.has(category)) return;
    let live = true;
    load(category).then(
      () => live && setDone((n) => n + 1),
      (error) => live && setFailed({ category, error }),
    );
    return () => {
      live = false;
    };
  }, [category]);

  const parts = loaded.get(category) ?? null;
  if (parts) return { parts, loading: false, error: null };
  if (failed?.category === category) return { parts: null, loading: false, error: failed.error };
  return { parts: null, loading: true, error: null };
}
