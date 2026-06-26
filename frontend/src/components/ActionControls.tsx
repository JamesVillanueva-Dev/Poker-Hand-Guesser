import { Play, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import type { ActionType, Street } from "../types/poker";

interface ActionControlsProps {
  onAction: (actionType: ActionType, street: Street, betFraction: number) => void;
  onStart: () => void;
  loading: boolean;
}

const actions: ActionType[] = ["check", "call", "bet", "raise", "three_bet", "jam", "fold"];
const streets: Street[] = ["preflop", "flop", "turn", "river"];

export function ActionControls({ onAction, onStart, loading }: ActionControlsProps) {
  const [actionType, setActionType] = useState<ActionType>("raise");
  const [street, setStreet] = useState<Street>("preflop");
  const [betFraction, setBetFraction] = useState(0.75);

  return (
    <section className="card-panel p-5 md:p-6">
      <div className="mb-4 flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Observed Action</h2>
          <p className="mt-2 text-base leading-7 text-zinc-600">Apply the opponent action you saw. The backend updates the posterior range immediately.</p>
        </div>
        <button
          className="inline-flex h-9 items-center gap-2 border border-zinc-300 px-3 text-sm font-medium hover:bg-zinc-50 disabled:opacity-50"
          style={{ borderRadius: 6 }}
          onClick={onStart}
          disabled={loading}
          title="Start a fresh hand session"
        >
          <RotateCcw size={16} />
          Reset
        </button>
      </div>
      <div className="grid gap-4 xl:grid-cols-[200px_220px_1fr_auto]">
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Street
          <select className="h-10 border border-zinc-300 bg-white px-3 text-sm capitalize text-ink" style={{ borderRadius: 6 }} value={street} onChange={(event) => setStreet(event.target.value as Street)}>
            {streets.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Action
          <select className="h-10 border border-zinc-300 bg-white px-3 text-sm capitalize text-ink" style={{ borderRadius: 6 }} value={actionType} onChange={(event) => setActionType(event.target.value as ActionType)}>
            {actions.map((item) => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
          </select>
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <span className="flex items-center gap-2"><SlidersHorizontal size={14} /> Bet Size / Pot</span>
          <div className="grid h-10 grid-cols-[1fr_62px] items-center gap-3 rounded-md border border-zinc-300 bg-white px-3">
            <input min={0} max={2} step={0.05} type="range" value={betFraction} onChange={(event) => setBetFraction(Number(event.target.value))} />
            <span className="mono-tabular text-right text-sm text-zinc-700">{Math.round(betFraction * 100)}%</span>
          </div>
        </label>
        <button
          className="inline-flex h-10 self-end items-center justify-center gap-2 bg-ink px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-felt-900 disabled:opacity-50"
          style={{ borderRadius: 6 }}
          onClick={() => onAction(actionType, street, betFraction)}
          disabled={loading}
          title="Update posterior range"
        >
          <Play size={16} />
          Apply
        </button>
      </div>
    </section>
  );
}
