"use client";

import { useT } from "@/lib/locale";

// `updatedIso`: catalogue date as YYYY-MM-DD; formatted in the chosen language.
export default function SiteFooter({ shops, updatedIso }) {
  const t = useT();
  const updated = new Date(updatedIso).toLocaleDateString(t.locale, { timeZone: "UTC" });
  return <footer className="site-footer">{t.footer(shops, updated)}</footer>;
}
