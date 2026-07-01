import { Play, RotateCcw, SlidersHorizontal, Sparkles } from "lucide-react";
import { useState } from "react";
import type { ActionActor, ActionDraft, ActionType, HandContext, Street } from "../types/poker";

interface ActionControlsProps {
  context: HandContext;
  onContext: (context: Partial<HandContext>) => void;
  onAction: (draft: ActionDraft) => void;
  onNewHand: () => void;
  onResetSession: () => void;
  loading: boolean;
}

const actions: ActionType[] = ["fold", "check", "call", "bet", "raise", "three_bet", "four_bet", "jam"];
const streets: Street[] = ["preflop", "flop", "turn", "river"];
const actors: ActionActor[] = ["opponent", "hero"];

export function ActionControls({ context, onContext, onAction, onNewHand, onResetSession, loading }: ActionControlsProps) {
  const [actor, setActor] = useState<ActionActor>("opponent");
  const [actionType, setActionType] = useState<ActionType>("raise");
  const [amount, setAmount] = useState(3);
  const betFraction = context.pot > 0 ? amount / context.pot : 0;

  return (
    <section className="card-panel p-5 md:p-6">
      <div className="mb-4 flex flex-col justify-between gap-3 md:flex-row md:items-center">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Heads-Up Action Entry</h2>
          <p className="mt-2 text-base leading-7 text-zinc-600">Log hero and opponent actions with real sizing. Opponent actions update the live range and session tendencies.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            className="inline-flex h-9 items-center gap-2 border border-zinc-300 px-3 text-sm font-medium hover:bg-zinc-50 disabled:opacity-50"
            style={{ borderRadius: 6 }}
            onClick={onNewHand}
            disabled={loading}
            title="Start the next hand and keep current session tendencies"
          >
            <Sparkles size={16} />
            New hand
          </button>
          <button
            className="inline-flex h-9 items-center gap-2 border border-zinc-300 px-3 text-sm font-medium hover:bg-zinc-50 disabled:opacity-50"
            style={{ borderRadius: 6 }}
            onClick={onResetSession}
            disabled={loading}
            title="Clear session tendencies and start over"
          >
            <RotateCcw size={16} />
            Reset session
          </button>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_1fr_1fr]">
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Hero Cards
          <input className="h-10 border border-zinc-300 bg-white px-3 text-sm text-ink" style={{ borderRadius: 6 }} value={context.heroCards} placeholder="Ah Kd" onChange={(event) => onContext({ heroCards: event.target.value })} />
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Board
          <input className="h-10 border border-zinc-300 bg-white px-3 text-sm text-ink" style={{ borderRadius: 6 }} value={context.boardCards} placeholder="As 7d 2c" onChange={(event) => onContext({ boardCards: event.target.value })} />
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Pot Before
          <input className="h-10 border border-zinc-300 bg-white px-3 text-sm text-ink" style={{ borderRadius: 6 }} min={0} step={0.5} type="number" value={context.pot} onChange={(event) => onContext({ pot: Number(event.target.value) })} />
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Effective Stack
          <input className="h-10 border border-zinc-300 bg-white px-3 text-sm text-ink" style={{ borderRadius: 6 }} min={0} step={1} type="number" value={context.effectiveStack} onChange={(event) => onContext({ effectiveStack: Number(event.target.value) })} />
        </label>
      </div>

      <div className="grid gap-4 xl:grid-cols-[170px_160px_180px_150px_1fr_auto]">
        <div className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Actor
          <div className="grid h-10 grid-cols-2 overflow-hidden border border-zinc-300 bg-white" style={{ borderRadius: 6 }}>
            {actors.map((item) => (
              <button key={item} className={`text-sm capitalize ${actor === item ? "bg-ink text-white" : "text-zinc-700 hover:bg-zinc-50"}`} onClick={() => setActor(item)} type="button">
                {item}
              </button>
            ))}
          </div>
        </div>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Street
          <select className="h-10 border border-zinc-300 bg-white px-3 text-sm capitalize text-ink" style={{ borderRadius: 6 }} value={context.street} onChange={(event) => onContext({ street: event.target.value as Street })}>
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
          Position
          <input className="h-10 border border-zinc-300 bg-white px-3 text-sm text-ink" style={{ borderRadius: 6 }} value={context.position} onChange={(event) => onContext({ position: event.target.value })} />
        </label>
        <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          <span className="flex items-center gap-2"><SlidersHorizontal size={14} /> Amount</span>
          <div className="grid h-10 grid-cols-[1fr_62px] items-center gap-3 rounded-md border border-zinc-300 bg-white px-3">
            <input min={0} max={Math.max(1, context.effectiveStack)} step={0.5} type="range" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
            <input className="w-full text-right text-sm text-zinc-700 outline-none" min={0} step={0.5} type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
          </div>
        </label>
        <button
          className="inline-flex h-10 self-end items-center justify-center gap-2 bg-ink px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-felt-900 disabled:opacity-50"
          style={{ borderRadius: 6 }}
          onClick={() => onAction({
            actor,
            action_type: actionType,
            street: context.street,
            position: context.position,
            amount: ["check", "fold"].includes(actionType) ? 0 : amount,
            pot_before: context.pot,
            board_cards: parseCards(context.boardCards),
            hero_cards: parseCards(context.heroCards).slice(0, 2),
            effective_stack: context.effectiveStack,
          })}
          disabled={loading}
          title="Apply this action"
        >
          <Play size={16} />
          Apply <span className="mono-tabular text-xs opacity-80">{Math.round(betFraction * 100)}%</span>
        </button>
      </div>
    </section>
  );
}

function parseCards(value: string): string[] {
  return value
    .split(/[\s,]+/)
    .map((card) => card.trim())
    .filter(Boolean)
    .map((card) => `${card[0]?.toUpperCase() ?? ""}${card[1]?.toLowerCase() ?? ""}`)
    .filter((card) => /^[AKQJT98765432][shdc]$/.test(card));
}
