import { Suspense } from "react";
import { getBuild } from "@/lib/api";
import { GAMES } from "@/mock/build";
import { t } from "@/strings";
import BuildResultView, { BackLink, LoadingCard } from "@/components/BuildResultView";

export default function BuildPage({ searchParams }) {
  return (
    <>
      <BackLink />
      <Suspense fallback={<LoadingCard />}>
        <BuildResult searchParams={searchParams} />
      </Suspense>
    </>
  );
}

// Fetches on the server; BuildResultView renders it in the user's language.
async function BuildResult({ searchParams }) {
  const params = await searchParams;
  const budget = Number(params.budget) || 1000;
  const game = params.game || "cs2";
  const exclude = (params.exclude || "").split(",").filter((c) => c in t.categories);
  const gameName = GAMES.find((g) => g.id === game)?.name ?? game;

  const build = await getBuild({ budget, game, exclude });
  return <BuildResultView build={build} gameName={gameName} exclude={exclude} />;
}
