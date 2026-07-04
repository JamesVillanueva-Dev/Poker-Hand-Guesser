import { ArrowDown, ArrowUp, Coins } from "lucide-react";
import type { ActionActor, HandContext, RangeResponse, Street } from "../types/poker";

interface PokerTableVisualizerProps {
  context: HandContext;
  range: RangeResponse;
  currentStreet: Street | "setup" | "showdown";
  villainCards?: string[];
}

const streets: Street[] = ["preflop", "flop", "turn", "river"];

function Card({ value, hidden = false }: { value?: string; hidden?: boolean }) {
  const red = value?.endsWith("h") || value?.endsWith("d");
  return (
    <span
      className={`inline-flex h-12 w-9 shrink-0 items-center justify-center border text-sm font-bold shadow-sm ${
        hidden
          ? "border-sky-300 text-white"
          : "border-sky-200 bg-white"
      } ${red ? "text-red-600" : "text-ink"}`}
      style={{
        borderRadius: 6,
        background: hidden ? "repeating-linear-gradient(135deg, #2563eb 0, #2563eb 6px, #38bdf8 6px, #38bdf8 12px)" : undefined,
      }}
    >
      {hidden ? "" : value || "--"}
    </span>
  );
}

function ActionPill({ label }: { label: string }) {
  return (
    <span className="inline-flex max-w-full items-center rounded-full bg-white px-2.5 py-1 text-xs font-medium text-zinc-600 ring-1 ring-sky-100">
      <span className="truncate">{label}</span>
    </span>
  );
}

function formatAction(entry: RangeResponse["timeline"][number]) {
  if (!entry.action) return entry.action_label;
  const label = entry.action.action_type.replace("_", " ");
  const amount = entry.action.amount > 0 ? ` ${entry.action.amount.toFixed(1)}bb` : "";
  return `${entry.action.actor} ${label}${amount}`;
}

function chipPosition(actor?: ActionActor) {
  if (actor === "hero") return "bottom-[31%] left-1/2 -translate-x-1/2";
  if (actor === "opponent") return "top-[31%] left-1/2 -translate-x-1/2";
  return "left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2";
}

export function PokerTableVisualizer({ context, range, currentStreet, villainCards = [] }: PokerTableVisualizerProps) {
  const heroCards = context.heroCards.trim() ? context.heroCards.split(/[\s,]+/).slice(0, 2) : range.board_state.hero_cards;
  const boardCards = context.boardCards.trim() ? context.boardCards.split(/[\s,]+/).slice(0, 5) : range.board_state.board_cards;
  const latestAction = [...range.timeline].reverse().find((entry) => entry.action)?.action;
  const latestAmount = latestAction?.amount ?? 0;
  const currentStreetIndex = currentStreet === "setup" ? -1 : currentStreet === "showdown" ? streets.length : streets.indexOf(currentStreet);

  const actionsByStreet = streets.reduce<Record<Street, RangeResponse["timeline"]>>((acc, street) => {
    acc[street] = range.timeline.filter((entry) => entry.action?.street === street);
    return acc;
  }, { preflop: [], flop: [], turn: [], river: [] });

  return (
    <div className="grid gap-4">
      <div className="relative min-h-[420px] overflow-hidden bg-sky-50 p-4 shadow-inner md:min-h-[480px]" style={{ borderRadius: 8 }}>
        <div className="absolute inset-x-5 top-24 bottom-24 rounded-[46%] border-[10px] border-sky-200 bg-gradient-to-b from-white to-sky-100 shadow-inner md:inset-x-12 md:top-28 md:bottom-28" />
        <div className="absolute inset-x-[14%] top-[34%] bottom-[34%] rounded-[46%] border border-sky-300 bg-sky-500/10" />

        <div className="absolute left-1/2 top-4 z-10 grid w-40 -translate-x-1/2 justify-items-center gap-2 rounded-md border border-sky-100 bg-white/95 px-3 py-2 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Villain</div>
          <div className="flex gap-1.5">
            {currentStreet === "showdown" && villainCards.length === 2 ? (
              villainCards.map((card, index) => <Card key={`${card}-${index}`} value={card} />)
            ) : (
              <>
                <Card hidden />
                <Card hidden />
              </>
            )}
          </div>
        </div>

        <div className="absolute left-1/2 top-1/2 z-10 grid -translate-x-1/2 -translate-y-1/2 justify-items-center gap-3">
          <div className="flex min-h-12 gap-1.5">
            {Array.from({ length: 5 }).map((_, index) => (
              <Card key={index} value={boardCards[index]} />
            ))}
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-2 text-sm font-semibold text-ink shadow-sm ring-1 ring-sky-100">
            <Coins size={17} className="text-copper" />
            Pot <span className="mono-tabular">{range.board_state.pot.toFixed(1)} bb</span>
          </div>
        </div>

        {latestAmount > 0 ? (
          <div className={`absolute z-10 ${chipPosition(latestAction?.actor)} transition-all duration-500`}>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-lg">
              {latestAction?.actor === "hero" ? <ArrowUp size={14} /> : <ArrowDown size={14} />}
              {latestAmount.toFixed(1)} bb
            </div>
          </div>
        ) : null}

        <div className="absolute bottom-4 left-1/2 z-10 grid w-40 -translate-x-1/2 justify-items-center gap-2 rounded-md border border-sky-100 bg-white/95 px-3 py-2 shadow-sm">
          <div className="flex gap-1.5">
            {heroCards.length ? heroCards.map((card, index) => <Card key={`${card}-${index}`} value={card} />) : (
              <>
                <Card />
                <Card />
              </>
            )}
          </div>
          <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Hero</div>
        </div>
      </div>

      <div className="grid gap-2 md:grid-cols-4">
        {streets.map((street, index) => {
          const complete = index < currentStreetIndex;
          const active = currentStreet === street;
          const entries = actionsByStreet[street];
          return (
            <div
              key={street}
              className={`min-w-0 border p-3 ${active ? "border-felt-700 bg-white" : complete ? "border-sky-100 bg-sky-50/70" : "border-zinc-200 bg-white/70"}`}
              style={{ borderRadius: 8 }}
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-zinc-600">{street}</span>
                <span className="text-xs text-zinc-500">{entries.length} actions</span>
              </div>
              <div className="grid gap-1.5">
                {entries.length ? entries.slice(-2).map((entry) => (
                  <ActionPill key={entry.sequence} label={formatAction(entry)} />
                )) : (
                  <span className="text-xs text-zinc-400">No actions</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
