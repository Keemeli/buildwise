import Link from "next/link";
import "./globals.css";
import { t, LOCALE } from "@/strings";
import { COMPONENTS, CATALOG_META } from "@/lib/catalog";

const shops = [...new Set(COMPONENTS.flatMap((c) => c.offers.map((o) => o.shop)))].sort().join(" · ");
const updated = new Date(CATALOG_META.generatedAt).toLocaleDateString(t.locale, { timeZone: "UTC" });

export const metadata = {
  title: t.meta.title,
  description: t.meta.description,
};

export default function RootLayout({ children }) {
  return (
    <html lang={LOCALE}>
      <body>
        <header className="site-header">
          <Link href="/" className="logo">
            Build<span>Wise</span>
          </Link>
        </header>
        <main className="container">{children}</main>
        <footer className="site-footer">
          {t.footer(shops, updated)}
        </footer>
      </body>
    </html>
  );
}
