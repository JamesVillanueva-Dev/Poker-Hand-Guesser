import { ArrowRight, Check, CircleDot, ClipboardList, Play, RotateCcw, Sparkles } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { ActionActor, ActionDraft, ActionType, HandContext, RangeResponse, Street } from "../types/poker";
import { PokerTableVisualizer } from "./PokerTableVisualizer";

interface GuidedHandFlowProps {
  context: HandContext;
  range: RangeResponse;
  handNumber: number;
  loading: boolean;
  onContext: (context: Partial<HandContext>) => void;
  onAction: (draft: ActionDraft) => void;
  onShowdown: (holeCards: string[], won: boolean) => Promise<void>;
  onNewHand: () => Promise<void>;
  onResetSession: () => Promise<void>;
}

type FlowStep = "setup" | Street | "showdown";

const streets: Street[] = ["preflop", "flop", "turn", "river"];
const actions: ActionType[] = ["fold", "check", "call", "bet", "raise", "three_bet", "four_bet", "jam"];
const actors: ActionActor[] = ["opponent", "hero"];
const ranks = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"];
const suits = [
  { value: "s", label: "Spades" },
  { value: "h", label: "Hearts" },
  { value: "d", label: "Diamonds" },
  { value: "c", label: "Clubs" },
];

const streetCopy: Record<Street, { title: string; boardLabel: string; boardPlaceholder: string; next: string }> = {
  preflop: {
    title: "Preflop Actions",
    boardLabel: "Board",
    boardPlaceholder: "No board yet",
    next: "Go to flop",
  },
  flop: {
    title: "Flop Actions",
    boardLabel: "Flop",
    boardPlaceholder: "As 7d 2c",
    next: "Go to turn",
  },
  turn: {
    title: "Turn Actions",
    boardLabel: "Flop + Turn",
    boardPlaceholder: "As 7d 2c Jh",
    next: "Go to river",
  },
  river: {
    title: "River Actions",
    boardLabel: "Full Board",
    boardPlaceholder: "As 7d 2c Jh 9s",
    next: "Show showdown",
  },
};

function nextStreet(step: Street): Street | undefined {
  return streets[streets.indexOf(step) + 1];
}

function parseCards(value: string): string[] {
  return value
    .split(/[\s,]+/)
    .map((card) => card.trim())
    .filter(Boolean)
    .map((card) => `${card[0]?.toUpperCase() ?? ""}${card[1]?.toLowerCase() ?? ""}`)
    .filter((card) => /^[AKQJT98765432][shdc]$/.test(card));
}

function formatAction(action: NonNullable<RangeResponse["timeline"][number]["action"]>) {
  const label = action.action_type.replace("_", " ");
  const amount = action.amount > 0 ? ` ${action.amount.toFixed(1)} bb` : "";
  return `${action.actor} ${label}${amount}`;
}

export function GuidedHandFlow({ context, range, handNumber, loading, onContext, onAction, onShowdown, onNewHand, onResetSession }: GuidedHandFlowProps) {
  const [step, setStep] = useState<FlowStep>("setup");
  const [actor, setActor] = useState<ActionActor>("opponent");
  const [actionType, setActionType] = useState<ActionType>("raise");
  const [amount, setAmount] = useState(3);
  const [villainRankOne, setVillainRankOne] = useState("A");
  const [villainSuitOne, setVillainSuitOne] = useState("s");
  const [villainRankTwo, setVillainRankTwo] = useState("K");
  const [villainSuitTwo, setVillainSuitTwo] = useState("h");
  const [villainWon, setVillainWon] = useState(false);

  useEffect(() => {
    setStep("setup");
    setActor("opponent");
    setActionType("raise");
    setAmount(3);
    setVillainRankOne("A");
    setVillainSuitOne("s");
    setVillainRankTwo("K");
    setVillainSuitTwo("h");
    setVillainWon(false);
  }, [handNumber]);

  const visibleStreet = step === "setup" || step === "showdown" ? context.street : step;
  const currentCopy = step === "setup" || step === "showdown" ? undefined : streetCopy[step];
  const betFraction = context.pot > 0 ? amount / context.pot : 0;
  const villainCards = [`${villainRankOne}${villainSuitOne}`, `${villainRankTwo}${villainSuitTwo}`];

  const actionsByStreet = useMemo(() => {
    return streets.reduce<Record<Street, RangeResponse["timeline"]>>((acc, street) => {
      acc[street] = range.timeline.filter((entry) => entry.action?.street === street);
      return acc;
    }, { preflop: [], flop: [], turn: [], river: [] });
  }, [range.timeline]);

  const moveNext = async () => {
    if (step === "setup") {
      onContext({ street: "preflop" });
      setStep("preflop");
      return;
    }
    if (step === "showdown") return;

    const next = nextStreet(step);
    if (next) {
      onContext({ street: next });
      setStep(next);
      setActor("opponent");
      setActionType(next === "flop" ? "bet" : actionType);
      return;
    }

    setStep("showdown");
  };

  const submitAction = () => {
    onAction({
      actor,
      action_type: actionType,
      street: visibleStreet,
      position: context.position,
      amount: ["check", "fold"].includes(actionType) ? 0 : amount,
      pot_before: context.pot,
      board_cards: parseCards(context.boardCards),
      hero_cards: parseCards(context.heroCards).slice(0, 2),
      effective_stack: context.effectiveStack,
    });
  };

  return (
    <section className="card-panel overflow-hidden">
      <div className="border-b border-sky-100 bg-white px-5 py-4 md:px-6">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-felt-700">Hand {handNumber}</div>
            <h1 className="mt-1 text-2xl font-semibold text-ink md:text-3xl">Guided Hand Entry</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">
              Only the current step is editable. Add hero actions when they matter, then advance streets with Next.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="inline-flex h-9 items-center gap-2 border border-sky-200 bg-white px-3 text-sm font-medium text-ink hover:bg-sky-50 disabled:opacity-50"
              style={{ borderRadius: 6 }}
              onClick={onNewHand}
              disabled={loading}
              title="Start the next hand and keep current session tendencies"
            >
              <Sparkles size={16} />
              New hand
            </button>
            <button
              className="inline-flex h-9 items-center gap-2 border border-sky-200 bg-white px-3 text-sm font-medium text-ink hover:bg-sky-50 disabled:opacity-50"
              style={{ borderRadius: 6 }}
              onClick={onResetSession}
              disabled={loading}
              title="Clear session tendencies and start over"
            >
              <RotateCcw size={16} />
              Reset
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-0 lg:grid-cols-[270px_1fr]">
        <aside className="border-b border-sky-100 bg-sky-50/50 p-4 lg:border-b-0 lg:border-r">
          <div className="grid gap-2">
            {(["setup", ...streets, "showdown"] as FlowStep[]).map((item) => {
              const active = step === item;
              const index = item === "setup" ? -1 : item === "showdown" ? streets.length : streets.indexOf(item);
              const currentIndex = step === "setup" ? -1 : step === "showdown" ? streets.length : streets.indexOf(step);
              const complete = item !== "showdown" && index < currentIndex;
              return (
                <div
                  key={item}
                  className={`flex items-center gap-3 border px-3 py-2 text-sm ${active ? "border-felt-700 bg-white text-ink shadow-sm" : complete ? "border-sky-100 bg-white/75 text-zinc-600" : "border-transparent text-zinc-500"}`}
                  style={{ borderRadius: 6 }}
                >
                  <span className={`inline-flex h-7 w-7 items-center justify-center rounded-full ${active ? "bg-felt-700 text-white" : complete ? "bg-felt-50 text-felt-700" : "bg-white text-zinc-400"}`}>
                    <CircleDot size={15} />
                  </span>
                  <span className="font-medium capitalize">{item === "setup" ? "Hero cards" : item}</span>
                </div>
              );
            })}
          </div>
        </aside>

        <div className="p-5 md:p-6">
          <PokerTableVisualizer context={context} range={range} currentStreet={step} villainCards={villainCards} />

          <div className="mt-6">
          {step === "setup" ? (
            <div className="grid gap-5">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Start With Hero Cards</h2>
                <p className="mt-2 text-sm leading-6 text-zinc-600">Hero cards are optional. Leave them blank if you only want to model the opponent.</p>
              </div>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Hero Cards
                  <input className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={context.heroCards} placeholder="Ah Kd" onChange={(event) => onContext({ heroCards: event.target.value })} />
                </label>
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Starting Pot
                  <input className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} min={0} step={0.5} type="number" value={context.pot} onChange={(event) => onContext({ pot: Number(event.target.value) })} />
                </label>
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Effective Stack
                  <input className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} min={0} step={1} type="number" value={context.effectiveStack} onChange={(event) => onContext({ effectiveStack: Number(event.target.value) })} />
                </label>
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Position
                  <input className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={context.position} onChange={(event) => onContext({ position: event.target.value })} />
                </label>
              </div>
            </div>
          ) : step === "showdown" ? (
            <div className="grid gap-5">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Showdown</h2>
                <p className="mt-2 text-sm leading-6 text-zinc-600">Select the two cards villain tabled, then record the result before moving to the next hand.</p>
              </div>

              <div className="grid gap-4 lg:grid-cols-[1fr_1fr_180px_auto]">
                <div className="grid gap-2">
                  <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Villain Card 1</div>
                  <div className="grid grid-cols-2 gap-2">
                    <select className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={villainRankOne} onChange={(event) => setVillainRankOne(event.target.value)}>
                      {ranks.map((rank) => <option key={rank} value={rank}>{rank}</option>)}
                    </select>
                    <select className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={villainSuitOne} onChange={(event) => setVillainSuitOne(event.target.value)}>
                      {suits.map((suit) => <option key={suit.value} value={suit.value}>{suit.label}</option>)}
                    </select>
                  </div>
                </div>
                <div className="grid gap-2">
                  <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">Villain Card 2</div>
                  <div className="grid grid-cols-2 gap-2">
                    <select className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={villainRankTwo} onChange={(event) => setVillainRankTwo(event.target.value)}>
                      {ranks.map((rank) => <option key={rank} value={rank}>{rank}</option>)}
                    </select>
                    <select className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={villainSuitTwo} onChange={(event) => setVillainSuitTwo(event.target.value)}>
                      {suits.map((suit) => <option key={suit.value} value={suit.value}>{suit.label}</option>)}
                    </select>
                  </div>
                </div>
                <label className="grid gap-2 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Result
                  <select className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={villainWon ? "villain" : "hero"} onChange={(event) => setVillainWon(event.target.value === "villain")}>
                    <option value="hero">Hero won</option>
                    <option value="villain">Villain won</option>
                  </select>
                </label>
                <button
                  className="inline-flex h-10 self-end items-center justify-center gap-2 bg-ink px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-felt-900 disabled:opacity-50"
                  style={{ borderRadius: 6 }}
                  onClick={() => onShowdown(villainCards, villainWon)}
                  disabled={loading || villainCards[0] === villainCards[1]}
                  title={villainCards[0] === villainCards[1] ? "Choose two different cards" : "Record showdown"}
                >
                  Record Showdown
                </button>
              </div>

              {villainCards[0] === villainCards[1] ? (
                <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900">Choose two different villain cards.</div>
              ) : null}
            </div>
          ) : (
            <div className="grid gap-5">
              <div className="flex flex-col justify-between gap-3 xl:flex-row xl:items-start">
                <div>
                  <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">{currentCopy?.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-zinc-600">Log one action at a time. Opponent actions update the range; hero actions are optional context.</p>
                </div>
                <div className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500 xl:w-72">
                  {currentCopy?.boardLabel}
                  <input
                    className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700 disabled:bg-sky-50"
                    style={{ borderRadius: 6 }}
                    value={context.boardCards}
                    placeholder={currentCopy?.boardPlaceholder}
                    onChange={(event) => onContext({ boardCards: event.target.value })}
                    disabled={step === "preflop"}
                  />
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-[170px_180px_150px_1fr_auto]">
                <div className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Actor
                  <div className="grid h-11 grid-cols-2 gap-1 border border-sky-200 bg-sky-50 p-1" style={{ borderRadius: 8 }}>
                    {actors.map((item) => (
                      <button
                        key={item}
                        aria-pressed={actor === item}
                        className={`inline-flex items-center justify-center gap-2 text-sm font-semibold capitalize transition ${
                          actor === item
                            ? "bg-felt-700 text-white shadow-sm ring-2 ring-sky-200"
                            : "bg-white text-zinc-600 hover:bg-sky-100 hover:text-ink"
                        }`}
                        style={{ borderRadius: 6 }}
                        onClick={() => setActor(item)}
                        type="button"
                      >
                        {actor === item ? <Check size={15} /> : null}
                        <span>{item}</span>
                      </button>
                    ))}
                  </div>
                </div>
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Action
                  <select className="h-10 border border-sky-200 bg-white px-3 text-sm capitalize text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} value={actionType} onChange={(event) => setActionType(event.target.value as ActionType)}>
                    {actions.map((item) => <option key={item} value={item}>{item.replace("_", " ")}</option>)}
                  </select>
                </label>
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Pot Before
                  <input className="h-10 border border-sky-200 bg-white px-3 text-sm text-ink outline-none focus:border-felt-700" style={{ borderRadius: 6 }} min={0} step={0.5} type="number" value={context.pot} onChange={(event) => onContext({ pot: Number(event.target.value) })} />
                </label>
                <label className="grid gap-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Amount
                  <div className="grid h-10 grid-cols-[1fr_68px] items-center gap-3 border border-sky-200 bg-white px-3" style={{ borderRadius: 6 }}>
                    <input className="accent-sky-500" disabled={["check", "fold"].includes(actionType)} min={0} max={Math.max(1, context.effectiveStack)} step={0.5} type="range" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
                    <input className="w-full text-right text-sm text-zinc-700 outline-none disabled:bg-transparent disabled:text-zinc-400" disabled={["check", "fold"].includes(actionType)} min={0} step={0.5} type="number" value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
                  </div>
                </label>
                <button
                  className="inline-flex h-10 self-end items-center justify-center gap-2 bg-ink px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-felt-900 disabled:opacity-50"
                  style={{ borderRadius: 6 }}
                  onClick={submitAction}
                  disabled={loading}
                  title="Apply this action"
                >
                  <Play size={16} />
                  Apply <span className="mono-tabular text-xs opacity-80">{Math.round(betFraction * 100)}%</span>
                </button>
              </div>

              <div className="rounded-md border border-sky-100 bg-sky-50/60 p-3">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-zinc-600">
                  <ClipboardList size={15} />
                  {visibleStreet} actions
                </div>
                <div className="grid gap-2">
                  {actionsByStreet[visibleStreet].length ? actionsByStreet[visibleStreet].map((entry) => (
                    <div key={entry.sequence} className="flex items-center justify-between gap-3 rounded-md bg-white px-3 py-2 text-sm">
                      <span className="font-medium capitalize">{entry.action ? formatAction(entry.action) : entry.action_label}</span>
                      <span className="mono-tabular text-xs text-zinc-500">#{entry.sequence}</span>
                    </div>
                  )) : (
                    <div className="rounded-md bg-white px-3 py-2 text-sm text-zinc-500">No actions logged for this street yet.</div>
                  )}
                </div>
              </div>
            </div>
          )}
          </div>

          <div className="mt-6 flex justify-end">
            <button
              className="inline-flex h-10 items-center justify-center gap-2 bg-felt-700 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-felt-900 disabled:opacity-50"
              style={{ borderRadius: 6 }}
              onClick={step === "showdown" ? onNewHand : moveNext}
              disabled={loading}
            >
              {step === "setup" ? "Start preflop" : step === "showdown" ? "Next hand" : currentCopy?.next}
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
