import Link from "next/link";
import "./globals.css";
import { t, DEFAULT_LOCALE } from "@/strings";
import LanguageSwitch from "@/components/LanguageSwitch";
import SiteFooter from "@/components/SiteFooter";
import BuilderLink from "@/components/BuilderLink";
import { CATALOG_META, SHOPS } from "@/lib/catalog";

export const metadata = {
  title: t.meta.title,
  description: t.meta.description,
};

export default function RootLayout({ children }) {
  return (
    <html lang={DEFAULT_LOCALE}>
      <body>
        <header className="site-header">
          <Link href="/" className="logo">
            Build<span>Wise</span>
          </Link>
          <nav className="site-nav">
            <BuilderLink />
            <LanguageSwitch />
          </nav>
        </header>
        <main className="container">{children}</main>
        <SiteFooter shops={SHOPS} updatedIso={CATALOG_META.generatedAt} />
      </body>
    </html>
  );
}
