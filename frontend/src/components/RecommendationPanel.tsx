import { BadgePercent, BrainCircuit, MoveUpRight } from "lucide-react";
import type { MoveRecommendation } from "../types/poker";

interface RecommendationPanelProps {
  recommendation: MoveRecommendation;
  notes: string[];
}

export function RecommendationPanel({ recommendation, notes }: RecommendationPanelProps) {
  return (
    <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <div className="card-panel p-5">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Best Move</h2>
            <div className="mt-2 flex flex-wrap items-end gap-3">
              <span className="text-3xl font-semibold capitalize text-ink">{recommendation.action}</span>
              {recommendation.sizing_bb > 0 ? (
                <span className="mono-tabular mb-1 text-sm font-medium text-zinc-600">
                  {recommendation.sizing_bb.toFixed(1)} bb / {Math.round(recommendation.sizing_pot_fraction * 100)}% pot
                </span>
              ) : null}
            </div>
          </div>
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-felt-50 text-felt-700">
            <MoveUpRight size={20} />
          </span>
        </div>
        <p className="text-sm leading-6 text-zinc-600">{recommendation.headline}</p>
        <div className="mt-4 grid gap-2">
          <div className="flex items-center justify-between text-xs font-medium uppercase tracking-wide text-zinc-500">
            <span>Confidence</span>
            <span className="mono-tabular">{Math.round(recommendation.confidence * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-zinc-100">
            <div className="h-full rounded-full bg-copper" style={{ width: `${Math.round(recommendation.confidence * 100)}%` }} />
          </div>
        </div>
      </div>

      <div className="card-panel p-5">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-zinc-600">
          <BrainCircuit size={17} className="text-felt-700" />
          Why It Changed
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded-md border border-zinc-200 bg-white p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
              <BadgePercent size={16} className="text-copper" />
              Recommendation Inputs
            </div>
            <ul className="grid gap-2 text-sm leading-5 text-zinc-600">
              {recommendation.reasons.slice(0, 3).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>
          <div className="rounded-md border border-zinc-200 bg-[#fbfcfc] p-3">
            <div className="mb-2 text-sm font-semibold text-ink">Session Adaptation</div>
            <ul className="grid gap-2 text-sm leading-5 text-zinc-600">
              {notes.slice(0, 3).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
