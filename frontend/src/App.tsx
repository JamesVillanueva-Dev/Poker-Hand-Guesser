import { useEffect, useRef } from "react";
import { GuidedHandFlow } from "./components/GuidedHandFlow";
import { PlayerStats } from "./components/PlayerStats";
import { RangeCharts } from "./components/RangeCharts";
import { RangeExplainer } from "./components/RangeExplainer";
import { RangeHeatmap } from "./components/RangeHeatmap";
import { RangeMetrics } from "./components/RangeMetrics";
import { RecommendationPanel } from "./components/RecommendationPanel";
import { Timeline } from "./components/Timeline";
import { TopHands } from "./components/TopHands";
import { useRangeStore } from "./store/rangeStore";

export default function App() {
  const { range, profile, handContext, handNumber, loading, error, selectedSequence, updateContext, newHand, resetSession, addAction, recordShowdown, rewind } = useRangeStore();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void resetSession();
  }, [resetSession]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dff4ff_0,#f6fbff_34%,#ffffff_100%)] px-4 py-6 text-ink md:px-8 md:py-8">
      <div className="mx-auto grid max-w-[1500px] gap-6">
        <GuidedHandFlow
          context={handContext}
          range={range}
          handNumber={handNumber}
          loading={loading}
          onContext={updateContext}
          onAction={addAction}
          onShowdown={recordShowdown}
          onNewHand={() => newHand(true)}
          onResetSession={resetSession}
        />
        {error ? <div className="border border-sky-300 bg-sky-50 px-4 py-3 text-sm text-sky-900" style={{ borderRadius: 6 }}>{error}</div> : null}
        <RecommendationPanel recommendation={range.recommendation} notes={range.adaptation_notes} />
        <section className="grid gap-5">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Analysis</h2>
            <p className="mt-1 text-sm text-zinc-600">The hand flow stays focused above; range details live here while the hand evolves.</p>
          </div>
          <RangeMetrics entropy={range.entropy} topHands={range.top_hands} matrix={range.matrix} />
          <div className="grid gap-6 2xl:grid-cols-[minmax(780px,1fr)_420px]">
            <RangeHeatmap matrix={range.matrix} />
            <TopHands hands={range.top_hands} />
          </div>
          <RangeExplainer timeline={range.timeline} topHands={range.top_hands} entropy={range.entropy} />
          <Timeline entries={range.timeline} selected={selectedSequence} onSelect={rewind} />
          <RangeCharts timeline={range.timeline} topHands={range.top_hands} />
          <PlayerStats profile={profile} />
        </section>
      </div>
    </main>
  );
}
