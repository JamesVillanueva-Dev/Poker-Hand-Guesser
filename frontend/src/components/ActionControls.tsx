import { Play, RotateCcw } from "lucide-react";
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
    <section className="card-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Observed Action</h2>
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
      <div className="grid gap-3 md:grid-cols-[1fr_1fr_1fr_auto]">
        <select className="h-10 border border-zinc-300 px-3 capitalize" style={{ borderRadius: 6 }} value={street} onChange={(event) => setStreet(event.target.value as Street)}>
          {streets.map((item) => <option key={item} value={item}>{item}</option>)}
        </select>
        <select className="h-10 border border-zinc-300 px-3 capitalize" style={{ borderRadius: 6 }} value={actionType} onChange={(event) => setActionType(event.target.value as ActionType)}>
          {actions.map((item) => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
        </select>
        <label className="grid grid-cols-[1fr_54px] items-center gap-3 text-sm">
          <input min={0} max={2} step={0.05} type="range" value={betFraction} onChange={(event) => setBetFraction(Number(event.target.value))} />
          <span className="mono-tabular text-right text-zinc-600">{Math.round(betFraction * 100)}%</span>
        </label>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 bg-ink px-4 text-sm font-semibold text-white hover:bg-felt-900 disabled:opacity-50"
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
