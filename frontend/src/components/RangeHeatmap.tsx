import { Grid3x3, List } from "lucide-react";
import { Fragment, useState } from "react";
import { RANKS } from "../lib/cards";
import { percent } from "../lib/format";
import { heatStyle, legendStops } from "../lib/scale";
import type { MatrixCell, TimelineEntry } from "../types/poker";

interface RangeHeatmapProps {
  matrix: MatrixCell[];
  timeline: TimelineEntry[];
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1e-9);
  const points = values
    .map((value, index) => `${(index / (values.length - 1)) * 100},${28 - (value / max) * 26}`)
    .join(" ");
  return (
    <svg viewBox="0 0 100 28" preserveAspectRatio="none" className="h-7 w-full" role="img" aria-label="Probability across the hand">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/**
 * The 169-class grid.
 *
 * Cells are buttons because they now do something: clicking one pins that class and
 * shows how its probability moved across the hand. Classes that card removal has ruled
 * out entirely are hatched, because "impossible" and "unlikely" are different facts and
 * the difference is one of the more useful things on this screen.
 */
export function RangeHeatmap({ matrix, timeline }: RangeHeatmapProps) {
  const [pinned, setPinned] = useState<string | null>(null);
  const [view, setView] = useState<"grid" | "list">("grid");

  const max = Math.max(...matrix.map((cell) => cell.probability), 1e-9);
  const byKey = new Map(matrix.map((cell) => [`${cell.row}-${cell.col}`, cell]));
  const sorted = [...matrix].sort((a, b) => b.probability - a.probability);
  // Only the leading cells carry a number; 169 of them at 11px is noise, not information.
  const labelled = new Set(sorted.slice(0, 12).map((cell) => cell.hand));
  const pinnedCell = pinned ? matrix.find((cell) => cell.hand === pinned) : undefined;
  const pinnedTrack = pinnedCell ? timeline.map((entry) => entry.distribution[pinnedCell.hand] ?? 0) : [];

  return (
    <section className="panel p-4 md:p-5" aria-labelledby="heatmap-heading">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="heatmap-heading" className="label-section">
            Range heatmap
          </h2>
          <p className="mt-1 text-body text-ink-muted">
            Darker cells hold more of the opponent's range. Select a class to track it through the hand.
          </p>
        </div>
        <div className="flex gap-1 rounded border border-line bg-surface-sunken p-0.5" role="group" aria-label="Heatmap view">
          {([
            { key: "grid", label: "Grid", Icon: Grid3x3 },
            { key: "list", label: "List", Icon: List },
          ] as const).map(({ key, label, Icon }) => (
            <button
              key={key}
              type="button"
              aria-pressed={view === key}
              onClick={() => setView(key)}
              className={`inline-flex h-7 items-center gap-1.5 rounded-sm px-2.5 text-caption font-semibold transition-colors ${
                view === key ? "bg-accent-600 text-white" : "text-ink-muted hover:bg-surface"
              }`}
            >
              <Icon size={13} aria-hidden />
              {label}
            </button>
          ))}
        </div>
      </div>

      {view === "grid" ? (
        <div className="overflow-x-auto">
          <div className="grid min-w-[26rem] grid-cols-[1.35rem_repeat(13,minmax(0,1fr))] gap-[3px]">
            <div />
            {RANKS.map((rank) => (
              <div key={rank} className="pb-1 text-center text-micro font-semibold text-ink-faint" aria-hidden>
                {rank}
              </div>
            ))}
            {RANKS.map((rank, row) => (
              <Fragment key={`${rank}-row`}>
                <div className="flex items-center justify-center text-micro font-semibold text-ink-faint" aria-hidden>
                  {rank}
                </div>
                {RANKS.map((_, col) => {
                  const cell = byKey.get(`${row}-${col}`);
                  if (!cell) return <div key={`${row}-${col}`} />;
                  const blocked = cell.combo_count === 0;
                  const style = heatStyle(cell.probability, max);
                  const selected = pinned === cell.hand;
                  return (
                    <button
                      key={`${row}-${col}`}
                      type="button"
                      aria-pressed={selected}
                      aria-label={`${cell.hand}: ${percent(cell.probability, 2)}, ${cell.combo_count} combos${blocked ? ", impossible on this board" : ""}`}
                      onClick={() => setPinned(selected ? null : cell.hand)}
                      className={`relative aspect-square rounded-sm text-[0.6rem] font-semibold leading-none transition-transform hover:z-10 hover:scale-110 ${
                        blocked ? "blocked-cell text-ink-faint" : ""
                      } ${selected ? "z-10 outline outline-2 outline-offset-1 outline-accent-600" : ""}`}
                      style={blocked ? undefined : { background: style.background, color: style.color }}
                    >
                      <span className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
                        <span className={blocked ? "line-through opacity-60" : ""}>{cell.hand}</span>
                        {labelled.has(cell.hand) && !blocked ? (
                          <span className="numeric text-[0.5rem] font-medium opacity-85">
                            {(cell.probability * 100).toFixed(1)}
                          </span>
                        ) : null}
                      </span>
                    </button>
                  );
                })}
              </Fragment>
            ))}
          </div>
        </div>
      ) : (
        <ol className="grid max-h-[28rem] gap-1 overflow-y-auto pr-1">
          {sorted.map((cell) => (
            <li key={cell.hand}>
              <button
                type="button"
                aria-pressed={pinned === cell.hand}
                onClick={() => setPinned(pinned === cell.hand ? null : cell.hand)}
                className={`grid w-full grid-cols-[3rem_1fr_4rem_4rem] items-center gap-2 rounded-sm px-2 py-1 text-left text-caption transition-colors hover:bg-accent-50 ${
                  pinned === cell.hand ? "bg-accent-50 ring-1 ring-accent-600" : ""
                }`}
              >
                <span className="font-semibold text-ink">{cell.hand}</span>
                <span className="h-2 overflow-hidden rounded-full bg-surface-sunken">
                  <span
                    className="block h-full rounded-full"
                    style={{ width: `${Math.max(1, (cell.probability / max) * 100)}%`, background: heatStyle(cell.probability, max).background }}
                  />
                </span>
                <span className="numeric text-right text-ink-muted">{percent(cell.probability, 2)}</span>
                <span className={`numeric text-right ${cell.combo_count === 0 ? "text-ink-faint line-through" : "text-ink-faint"}`}>
                  {cell.combo_count} combo{cell.combo_count === 1 ? "" : "s"}
                </span>
              </button>
            </li>
          ))}
        </ol>
      )}

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-3">
        <div className="flex items-center gap-2">
          <span className="text-micro text-ink-faint">0%</span>
          {/* The endpoints carry the scale; the swatches are decoration between them. */}
          <div className="flex overflow-hidden rounded-sm border border-line" aria-hidden>
            {legendStops(max).map((stop) => (
              <span key={stop.probability} className="h-3 w-7" style={{ background: stop.background }} />
            ))}
          </div>
          <span className="numeric text-micro text-ink-faint">{percent(max, 2)}</span>
        </div>
        <div className="flex items-center gap-2 text-micro text-ink-faint">
          <span className="blocked-cell inline-block h-3 w-5 rounded-sm border border-line" aria-hidden />
          Impossible: every combo is blocked by a known card
        </div>
      </div>

      {pinnedCell ? (
        <div className="mt-3 grid gap-2 rounded border border-accent-200 bg-accent-50 p-3 md:grid-cols-[auto_1fr]">
          <div>
            <div className="text-title font-semibold text-ink">{pinnedCell.hand}</div>
            <div className="numeric text-caption text-ink-muted">
              {percent(pinnedCell.probability, 2)} · {pinnedCell.combo_count} live combo
              {pinnedCell.combo_count === 1 ? "" : "s"}
            </div>
          </div>
          <div className="text-accent-700">
            <Sparkline values={pinnedTrack} />
            <div className="text-micro text-ink-faint">Probability across {pinnedTrack.length} snapshots in this hand</div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
