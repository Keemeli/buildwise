"use client";

import Link from "next/link";
import { useT } from "@/lib/locale";

export default function BuilderLink() {
  const t = useT();
  return (
    <Link href="/builder" className="nav-link">
      {t.nav.builder}
    </Link>
  );
}
