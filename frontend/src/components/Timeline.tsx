import { GitBranch } from "lucide-react";
import type { TimelineEntry } from "../types/poker";

export function Timeline({ entries, selected, onSelect }: { entries: TimelineEntry[]; selected: number; onSelect: (sequence: number) => void }) {
  return (
    <section className="card-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Action Timeline</h2>
        <GitBranch size={16} className="text-zinc-500" />
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {entries.map((entry) => (
          <button
            key={entry.sequence}
            className={`min-w-36 border px-3 py-2 text-left text-sm transition ${selected === entry.sequence ? "border-felt-700 bg-felt-50" : "border-zinc-200 bg-white hover:bg-zinc-50"}`}
            style={{ borderRadius: 6 }}
            onClick={() => onSelect(entry.sequence)}
            title="Rewind belief distribution to this action"
          >
            <div className="text-xs font-medium text-zinc-500">#{entry.sequence}</div>
            <div className="truncate font-semibold">{entry.action_label}</div>
            <div className="mono-tabular text-xs text-zinc-500">Entropy {entry.entropy.toFixed(2)}</div>
          </button>
        ))}
      </div>
    </section>
  );
}
