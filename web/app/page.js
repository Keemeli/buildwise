import Landing from "@/components/Landing";
import { COMPONENTS, CATALOG_META, SHOPS } from "@/lib/catalog";

// Front page. The catalogue is read on the server so the landing page can show real
// numbers (how many parts, which shops, when updated) without shipping the data.
export default function HomePage() {
  return <Landing partCount={COMPONENTS.length} shops={SHOPS} updatedIso={CATALOG_META.generatedAt} />;
}
