import { useEffect, useRef } from "react";
import { ActionControls } from "./components/ActionControls";
import { HandSummary } from "./components/HandSummary";
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
  const { range, profile, handContext, handNumber, loading, error, selectedSequence, updateContext, newHand, resetSession, addAction, rewind } = useRangeStore();
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void resetSession();
  }, [resetSession]);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#e8f3ee_0,#f4f7f6_32%,#f7f7f5_100%)] px-4 py-6 text-ink md:px-8 md:py-8">
      <div className="mx-auto grid max-w-[1500px] gap-6">
        <HandSummary board={range.board_state} handNumber={handNumber} />
        <RangeMetrics entropy={range.entropy} topHands={range.top_hands} matrix={range.matrix} />
        <ActionControls context={handContext} onContext={updateContext} onAction={addAction} onNewHand={() => newHand(true)} onResetSession={resetSession} loading={loading} />
        {error ? <div className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900" style={{ borderRadius: 6 }}>{error}</div> : null}
        <RecommendationPanel recommendation={range.recommendation} notes={range.adaptation_notes} />
        <div className="grid gap-6 2xl:grid-cols-[minmax(780px,1fr)_420px]">
          <RangeHeatmap matrix={range.matrix} />
          <TopHands hands={range.top_hands} />
        </div>
        <RangeExplainer timeline={range.timeline} topHands={range.top_hands} entropy={range.entropy} />
        <Timeline entries={range.timeline} selected={selectedSequence} onSelect={rewind} />
        <RangeCharts timeline={range.timeline} topHands={range.top_hands} />
        <PlayerStats profile={profile} />
      </div>
    </main>
  );
}
