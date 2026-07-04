import { Fragment } from "react";
import type { MatrixCell } from "../types/poker";
import { ranks } from "../store/handClasses";

interface RangeHeatmapProps {
  matrix: MatrixCell[];
}

function colorFor(probability: number, maxProbability: number) {
  const intensity = maxProbability > 0 ? probability / maxProbability : 0;
  const lightness = 97 - intensity * 48;
  const saturation = 58 + intensity * 28;
  return `hsl(${202 + intensity * 12} ${saturation}% ${lightness}%)`;
}

export function RangeHeatmap({ matrix }: RangeHeatmapProps) {
  const maxProbability = Math.max(...matrix.map((cell) => cell.probability), 0.001);
  const byKey = new Map(matrix.map((cell) => [`${cell.row}-${cell.col}`, cell]));

  return (
    <section className="card-panel p-5 md:p-6">
      <div className="mb-5 flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Range Heatmap</h2>
          <p className="mt-2 text-base leading-7 text-zinc-600">Darker cells hold more probability in the current posterior distribution.</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span>Low</span>
          <div className="h-2 w-28 rounded-full bg-gradient-to-r from-[#eef9ff] to-[#2563eb]" />
          <span>High</span>
        </div>
      </div>
      <div className="overflow-x-auto pb-2">
        <div className="grid min-w-[820px] grid-cols-[30px_repeat(13,minmax(0,1fr))] gap-1.5">
          <div />
          {ranks.map((rank) => (
            <div key={rank} className="text-center text-xs font-semibold text-zinc-500">
              {rank}
            </div>
          ))}
          {ranks.map((rank, row) => (
            <Fragment key={`${rank}-row`}>
              <div key={`${rank}-label`} className="flex items-center justify-center text-xs font-semibold text-zinc-500">
                {rank}
              </div>
              {ranks.map((_, col) => {
                const cell = byKey.get(`${row}-${col}`);
                const probability = cell?.probability ?? 0;
                return (
                  <button
                    key={`${row}-${col}`}
                    className="aspect-square min-h-12 border border-white text-xs font-semibold text-ink transition hover:scale-[1.03] hover:border-sky-700 focus:outline-none focus:ring-2 focus:ring-copper"
                    style={{ background: colorFor(probability, maxProbability), borderRadius: 5 }}
                    title={`${cell?.hand ?? ""} | ${(probability * 100).toFixed(3)}% | ${cell?.combo_count ?? 0} combos`}
                  >
                    <span className="block leading-tight">{cell?.hand}</span>
                    <span className="mt-0.5 block text-[11px] font-medium opacity-75">{(probability * 100).toFixed(1)}%</span>
                  </button>
                );
              })}
            </Fragment>
          ))}
        </div>
      </div>
    </section>
  );
}
