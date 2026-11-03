import Link from "next/link";
import "./globals.css";
import { t, LOCALE } from "@/strings";

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
          {t.footer}
        </footer>
      </body>
    </html>
  );
}
