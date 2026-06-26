import { useEffect } from "react";
import { ActionControls } from "./components/ActionControls";
import { HandSummary } from "./components/HandSummary";
import { PlayerStats } from "./components/PlayerStats";
import { RangeCharts } from "./components/RangeCharts";
import { RangeHeatmap } from "./components/RangeHeatmap";
import { Timeline } from "./components/Timeline";
import { TopHands } from "./components/TopHands";
import { useRangeStore } from "./store/rangeStore";

export default function App() {
  const { range, profile, loading, error, selectedSequence, start, addAction, rewind } = useRangeStore();

  useEffect(() => {
    void start();
  }, [start]);

  return (
    <main className="min-h-screen bg-[#f4f7f6] px-4 py-5 text-ink md:px-6">
      <div className="mx-auto grid max-w-7xl gap-4">
        <HandSummary board={range.board_state} />
        <ActionControls onAction={addAction} onStart={start} loading={loading} />
        {error ? <div className="border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900" style={{ borderRadius: 6 }}>{error}</div> : null}
        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.6fr)]">
          <RangeHeatmap matrix={range.matrix} />
          <TopHands hands={range.top_hands} />
        </div>
        <Timeline entries={range.timeline} selected={selectedSequence} onSelect={rewind} />
        <RangeCharts timeline={range.timeline} topHands={range.top_hands} />
        <PlayerStats profile={profile} />
      </div>
    </main>
  );
}
