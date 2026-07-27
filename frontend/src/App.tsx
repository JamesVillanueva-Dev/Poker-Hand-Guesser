import { useEffect, useMemo, useRef, useState } from "react";
import { AnswerHeader } from "./components/AnswerHeader";
import { CalibrationPanel } from "./components/CalibrationPanel";
import { HandEntry } from "./components/HandEntry";
import { PlayerStats } from "./components/PlayerStats";
import { RangeCharts } from "./components/RangeCharts";
import { RangeExplainer } from "./components/RangeExplainer";
import { RangeHeatmap } from "./components/RangeHeatmap";
import { AnswerSkeleton, BackendOffline, ErrorBanner, ShortcutOverlay } from "./components/States";
import { Tabs } from "./components/Tabs";
import { Timeline } from "./components/Timeline";
import { TopHands } from "./components/TopHands";
import { useHotkeys } from "./hooks/useHotkeys";
import { useRangeStore } from "./store/rangeStore";

export default function App() {
  const {
    range,
    profile,
    handContext,
    handNumber,
    loading,
    error,
    selectedSequence,
    updateContext,
    dismissError,
    newHand,
    resetSession,
    addAction,
    recordShowdown,
    rewind,
  } = useRangeStore();

  const [tab, setTab] = useState("timeline");
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    void resetSession();
  }, [resetSession]);

  const stepBack = () => {
    if (!range || selectedSequence <= 0) return;
    void rewind(selectedSequence - 1);
  };

  useHotkeys(
    useMemo(
      () => ({
        ArrowLeft: stepBack,
        Escape: () => setShortcutsOpen(false),
      }),
      [stepBack],
    ),
  );

  const baselineEntropy = range?.calibration.baseline_log_loss ?? 7.4;

  const tabs = range
    ? [
        {
          id: "timeline",
          label: "Rewind",
          content: <Timeline entries={range.timeline} selected={selectedSequence} onSelect={rewind} />,
        },
        {
          id: "accuracy",
          label: "Accuracy",
          content: <CalibrationPanel calibration={range.calibration} />,
        },
        {
          id: "opponent",
          label: "Opponent",
          content: <PlayerStats profile={profile} samples={range.profile_samples} />,
        },
        {
          id: "trends",
          label: "Trends",
          content: (
            <RangeCharts timeline={range.timeline} topHands={range.top_hands} baselineEntropy={baselineEntropy} />
          ),
        },
      ]
    : [];

  return (
    <div className="min-h-screen bg-surface-sunken text-ink">
      <div className="mx-auto grid max-w-[100rem] gap-4 px-4 py-4 lg:grid-cols-[23rem_minmax(0,1fr)] lg:items-start lg:gap-6 lg:px-6 lg:py-6">
        {/* No overflow clipping here, and an explicit z-index: `position: sticky` opens a
            stacking context, so without one the card picker's popover paints *under* the
            opaque panels in the reading region instead of over them. */}
        <aside className="panel z-20 h-fit p-4 lg:sticky lg:top-6 lg:p-5">
          {range ? (
            <HandEntry
              context={handContext}
              range={range}
              handNumber={handNumber}
              loading={loading}
              onContext={updateContext}
              onAction={addAction}
              onShowdown={recordShowdown}
              onNewHand={() => newHand(true)}
              onResetSession={resetSession}
              onShowShortcuts={() => setShortcutsOpen(true)}
            />
          ) : (
            <div className="grid gap-3">
              <div className="label-section">Hand entry</div>
              <p className="text-body text-ink-muted">Controls appear once the engine is reachable.</p>
            </div>
          )}
        </aside>

        <main className="grid min-w-0 gap-4">
          {error ? (
            <ErrorBanner
              error={error}
              onDismiss={dismissError}
              onNewHand={() => void newHand(true)}
              onRetry={() => void resetSession()}
            />
          ) : null}

          {!range ? (
            <BackendOffline error={error} loading={loading} onRetry={resetSession} />
          ) : loading && range.timeline.length === 0 ? (
            <AnswerSkeleton />
          ) : (
            <>
              <AnswerHeader
                recommendation={range.recommendation}
                calibration={range.calibration}
                entropy={range.entropy}
              />
              <div className="grid min-w-0 gap-4 2xl:grid-cols-[minmax(0,1fr)_22rem]">
                <RangeHeatmap matrix={range.matrix} timeline={range.timeline} />
                <TopHands hands={range.top_hands} composition={range.recommendation.range_composition} />
              </div>
              <Tabs tabs={tabs} active={tab} onChange={setTab} label="Hand details" />
              <RangeExplainer matrix={range.matrix} entropy={range.entropy} baselineEntropy={baselineEntropy} />
            </>
          )}
        </main>
      </div>

      {shortcutsOpen ? <ShortcutOverlay onClose={() => setShortcutsOpen(false)} /> : null}
    </div>
  );
}
