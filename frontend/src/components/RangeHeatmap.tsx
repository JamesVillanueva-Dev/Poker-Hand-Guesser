import { Fragment } from "react";
import type { MatrixCell } from "../types/poker";
import { ranks } from "../store/handClasses";

interface RangeHeatmapProps {
  matrix: MatrixCell[];
}

function colorFor(probability: number, maxProbability: number) {
  const intensity = maxProbability > 0 ? probability / maxProbability : 0;
  const lightness = 96 - intensity * 50;
  const saturation = 38 + intensity * 35;
  return `hsl(${155 - intensity * 32} ${saturation}% ${lightness}%)`;
}

export function RangeHeatmap({ matrix }: RangeHeatmapProps) {
  const maxProbability = Math.max(...matrix.map((cell) => cell.probability), 0.001);
  const byKey = new Map(matrix.map((cell) => [`${cell.row}-${cell.col}`, cell]));

  return (
    <section className="card-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Range Heatmap</h2>
        <span className="text-xs text-zinc-500">13x13 starting hands</span>
      </div>
      <div className="grid grid-cols-[24px_repeat(13,minmax(0,1fr))] gap-1">
        <div />
        {ranks.map((rank) => (
          <div key={rank} className="text-center text-[11px] font-semibold text-zinc-500">
            {rank}
          </div>
        ))}
        {ranks.map((rank, row) => (
          <Fragment key={`${rank}-row`}>
            <div key={`${rank}-label`} className="flex items-center justify-center text-[11px] font-semibold text-zinc-500">
              {rank}
            </div>
            {ranks.map((_, col) => {
              const cell = byKey.get(`${row}-${col}`);
              const probability = cell?.probability ?? 0;
              return (
                <button
                  key={`${row}-${col}`}
                  className="aspect-square min-h-8 border border-white text-[10px] font-semibold text-ink transition hover:scale-[1.04] hover:border-zinc-700 focus:outline-none focus:ring-2 focus:ring-copper"
                  style={{ background: colorFor(probability, maxProbability), borderRadius: 4 }}
                  title={`${cell?.hand ?? ""} | ${(probability * 100).toFixed(3)}% | ${cell?.combo_count ?? 0} combos`}
                >
                  <span className="block leading-tight">{cell?.hand}</span>
                  <span className="block text-[9px] font-medium opacity-70">{(probability * 100).toFixed(1)}</span>
                </button>
              );
            })}
          </Fragment>
        ))}
      </div>
    </section>
  );
}
