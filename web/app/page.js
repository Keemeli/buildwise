import Landing from "@/components/Landing";
import { COMPONENTS, CATALOG_META } from "@/lib/catalog";

// Front page. The catalogue is read on the server so the landing page can show real
// numbers (how many parts, which shops, when updated) without shipping the data.
const shops = [...new Set(COMPONENTS.flatMap((c) => c.offers.map((o) => o.shop)))].sort().join(" · ");

export default function HomePage() {
  return <Landing partCount={COMPONENTS.length} shops={shops} updatedIso={CATALOG_META.generatedAt} />;
}
