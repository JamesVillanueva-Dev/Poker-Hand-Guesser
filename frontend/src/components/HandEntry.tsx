import { ArrowRight, Check, Keyboard, Pencil, Play, RotateCcw, Sparkles, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useHotkeys } from "../hooks/useHotkeys";
import { bb, percent } from "../lib/format";
import { ACTION_LABELS, SIZED_ACTIONS, boardSizeFor, derivedPot, usedCards } from "../store/rangeStore";
import type { ActionActor, ActionDraft, ActionType, HandContext, RangeResponse, Street } from "../types/poker";
import { CardPicker } from "./CardPicker";
import { TableStrip } from "./TableStrip";

const STREETS: Street[] = ["preflop", "flop", "turn", "river"];
const SIZE_PRESETS: Array<{ label: string; fraction: number }> = [
  { label: "33%", fraction: 0.33 },
  { label: "50%", fraction: 0.5 },
  { label: "66%", fraction: 0.66 },
  { label: "Pot", fraction: 1 },
];

interface HandEntryProps {
  context: HandContext;
  range: RangeResponse;
  handNumber: number;
  loading: boolean;
  onContext: (context: Partial<HandContext>) => void;
  onAction: (draft: ActionDraft) => void;
  onShowdown: (holeCards: string[], won: boolean) => Promise<void>;
  onNewHand: () => Promise<void>;
  onResetSession: () => Promise<void>;
  onShowShortcuts: () => void;
}

/**
 * Everything the user touches, in one rail that does not scroll away from the answer.
 *
 * Two things it deliberately never asks for: the pot, which is derived from the hand so
 * far, and an illegal action, because the backend tells it which actions exist in this
 * spot.
 */
export function HandEntry({
  context,
  range,
  handNumber,
  loading,
  onContext,
  onAction,
  onShowdown,
  onNewHand,
  onResetSession,
  onShowShortcuts,
}: HandEntryProps) {
  const [actor, setActor] = useState<ActionActor>("opponent");
  const [actionType, setActionType] = useState<ActionType | null>(null);
  const [amount, setAmount] = useState(3);
  const [showdownOpen, setShowdownOpen] = useState(false);
  const [villainCards, setVillainCards] = useState<string[]>([]);
  const [villainWon, setVillainWon] = useState(false);
  const [editingPot, setEditingPot] = useState(false);

  const complete = range.hand_complete;
  const pot = derivedPot(range, context);
  const boardSize = boardSizeFor(context.street);

  // Hero can take any action; only the opponent's options are constrained by the read.
  // Keyed by street, so moving to the flop before logging anything there updates the
  // controls immediately. An empty list means this street's action is closed, which is
  // different from the hand being over, and different again from hero's free choice.
  const streetActions = range.legal_actions_by_street?.[context.street] ?? [];
  const streetClosed = !complete && streetActions.length === 0;
  const legal = useMemo<ActionType[]>(() => {
    if (complete || streetClosed) return [];
    if (actor === "hero") return ["fold", "check", "call", "bet", "raise", "three_bet", "four_bet", "jam"];
    return streetActions;
  }, [actor, complete, streetClosed, streetActions]);

  useEffect(() => {
    if (actionType && legal.includes(actionType)) return;
    setActionType(legal[0] ?? null);
  }, [legal, actionType]);

  useEffect(() => {
    setShowdownOpen(false);
    setVillainCards([]);
    setVillainWon(false);
    setActor("opponent");
  }, [handNumber]);

  const needsSize = actionType !== null && SIZED_ACTIONS.includes(actionType);
  const fraction = pot > 0 ? amount / pot : 0;

  const apply = () => {
    if (!actionType || complete || loading) return;
    onAction({
      actor,
      action_type: actionType,
      street: context.street,
      position: context.position,
      amount: needsSize ? amount : 0,
      pot_before: pot,
      board_cards: context.boardCards,
      hero_cards: context.heroCards.slice(0, 2),
      effective_stack: context.effectiveStack,
    });
  };

  const advanceStreet = () => {
    const next = STREETS[STREETS.indexOf(context.street) + 1];
    if (next) {
      onContext({ street: next });
      return;
    }
    setShowdownOpen(true);
  };

  useHotkeys(
    useMemo(
      () => ({
        ...Object.fromEntries(
          legal.slice(0, 5).map((action, index) => [String(index + 1), () => setActionType(action)]),
        ),
        Enter: apply,
        ArrowRight: advanceStreet,
        "?": onShowShortcuts,
      }),
      [legal, apply, advanceStreet, onShowShortcuts],
    ),
    !showdownOpen,
  );

  return (
    <div className="grid gap-4">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="label-section">Hand {handNumber}</div>
          <h1 className="text-page font-semibold text-ink">Hand entry</h1>
        </div>
        <div className="flex gap-1.5">
          <button className="btn btn-sm btn-secondary" onClick={onNewHand} disabled={loading}>
            <Sparkles size={14} aria-hidden />
            New hand
          </button>
          <button
            className="btn btn-sm btn-ghost"
            onClick={onResetSession}
            disabled={loading}
            aria-label="Reset session and clear all learned opponent tendencies"
          >
            <RotateCcw size={14} aria-hidden />
            Reset
          </button>
          <button className="btn btn-sm btn-ghost" onClick={onShowShortcuts} aria-label="Keyboard shortcuts">
            <Keyboard size={14} aria-hidden />
          </button>
        </div>
      </header>

      <nav aria-label="Street" className="grid grid-cols-4 gap-1 rounded border border-line bg-surface-sunken p-1">
        {STREETS.map((street) => {
          const index = STREETS.indexOf(street);
          const current = STREETS.indexOf(context.street);
          const active = street === context.street;
          return (
            <button
              key={street}
              type="button"
              aria-current={active ? "step" : undefined}
              onClick={() => onContext({ street })}
              className={`h-8 rounded-sm text-caption font-semibold capitalize transition-colors ${
                active
                  ? "bg-accent-600 text-white"
                  : index < current
                    ? "bg-surface text-ink-muted hover:bg-accent-50"
                    : "text-ink-faint hover:bg-surface"
              }`}
            >
              {street}
            </button>
          );
        })}
      </nav>

      <TableStrip
        heroCards={context.heroCards}
        boardCards={context.boardCards}
        villainCards={villainCards}
        pot={pot}
        street={context.street}
        potIsOverridden={context.potOverride !== undefined}
      />

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
        <CardPicker
          label="Hero cards"
          count={2}
          value={context.heroCards}
          taken={usedCards({ ...context, heroCards: [] }, villainCards)}
          onChange={(cards) => onContext({ heroCards: cards })}
          hint="optional"
          compact
        />
        {boardSize > 0 ? (
          <CardPicker
            label={context.street === "flop" ? "Flop" : context.street === "turn" ? "Board + turn" : "Full board"}
            count={boardSize}
            value={context.boardCards.slice(0, boardSize)}
            taken={usedCards({ ...context, boardCards: [] }, villainCards)}
            onChange={(cards) => onContext({ boardCards: cards })}
            compact
          />
        ) : null}
      </div>

      <div className="grid gap-3 border-t border-line pt-4">
        <div className="flex items-center justify-between gap-2">
          <span className="label-field">Who acted</span>
          <div className="flex gap-1 rounded border border-line bg-surface-sunken p-0.5">
            {(["opponent", "hero"] as ActionActor[]).map((option) => (
              <button
                key={option}
                type="button"
                aria-pressed={actor === option}
                onClick={() => setActor(option)}
                className={`h-7 rounded-sm px-3 text-caption font-semibold capitalize transition-colors ${
                  actor === option ? "bg-accent-600 text-white" : "text-ink-muted hover:bg-surface"
                }`}
              >
                {option}
              </button>
            ))}
          </div>
        </div>

        <div className="grid gap-1.5">
          <span className="label-field">
            Action
            {actor === "opponent" ? <span className="ml-1 text-micro text-ink-faint">(legal here)</span> : null}
          </span>
          {complete ? (
            <p className="text-caption text-ink-muted">This hand is over. Start the next one to keep modelling.</p>
          ) : streetClosed ? (
            <p className="text-caption text-ink-muted">
              The {context.street} action is complete. Move to the next street to keep logging.
            </p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {legal.map((action, index) => (
                <button
                  key={action}
                  type="button"
                  aria-pressed={actionType === action}
                  onClick={() => setActionType(action)}
                  className={`btn btn-sm ${actionType === action ? "btn-primary" : "btn-secondary"}`}
                >
                  {ACTION_LABELS[action]}
                  {index < 5 ? <kbd className="keycap">{index + 1}</kbd> : null}
                </button>
              ))}
            </div>
          )}
        </div>

        {needsSize && !complete ? (
          <div className="grid gap-1.5">
            <div className="flex items-baseline justify-between gap-2">
              <span className="label-field">Size</span>
              <span className="numeric text-caption text-ink-muted">
                {bb(amount)} · {percent(fraction, 0)} pot
              </span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {SIZE_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  className="btn btn-sm btn-secondary"
                  onClick={() => setAmount(Number((pot * preset.fraction).toFixed(1)))}
                >
                  {preset.label}
                </button>
              ))}
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => setAmount(context.effectiveStack)}
              >
                All-in
              </button>
              <label className="ml-auto flex items-center gap-1.5">
                <span className="sr-only">Exact amount in big blinds</span>
                <input
                  className="field numeric h-8 w-24 text-caption"
                  type="number"
                  min={0}
                  step={0.5}
                  value={amount}
                  onChange={(event) => setAmount(Number(event.target.value))}
                />
                <span className="text-caption text-ink-faint">bb</span>
              </label>
            </div>
          </div>
        ) : null}

        <div className="flex items-center justify-between gap-2 text-caption text-ink-muted">
          <span>
            Pot into this action <span className="numeric font-semibold text-ink">{bb(pot)}</span>
          </span>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={() => setEditingPot((open) => !open)}
            aria-expanded={editingPot}
          >
            <Pencil size={12} aria-hidden />
            {context.potOverride === undefined ? "Override" : "Overridden"}
          </button>
        </div>

        {editingPot ? (
          <div className="panel-sunken grid gap-2 p-3">
            <p className="text-caption text-ink-muted">
              The pot is derived from every action logged so far. Override it only when reconstructing a hand from
              partway through.
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="grid gap-1">
                <span className="label-field">Pot</span>
                <input
                  className="field numeric h-8 w-28 text-caption"
                  type="number"
                  min={0}
                  step={0.5}
                  value={context.potOverride ?? pot}
                  onChange={(event) => onContext({ potOverride: Number(event.target.value) })}
                />
              </label>
              <label className="grid gap-1">
                <span className="label-field">Effective stack</span>
                <input
                  className="field numeric h-8 w-28 text-caption"
                  type="number"
                  min={0}
                  step={1}
                  value={context.effectiveStack}
                  onChange={(event) => onContext({ effectiveStack: Number(event.target.value) })}
                />
              </label>
              <label className="grid gap-1">
                <span className="label-field">Position</span>
                <input
                  className="field h-8 w-24 text-caption"
                  value={context.position}
                  onChange={(event) => onContext({ position: event.target.value })}
                />
              </label>
              {context.potOverride !== undefined ? (
                <button className="btn btn-sm btn-ghost" onClick={() => onContext({ potOverride: undefined })}>
                  Use derived
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        <div className="flex gap-2">
          {complete ? (
            <button className="btn btn-md btn-primary flex-1" onClick={onNewHand} disabled={loading}>
              <Sparkles size={15} aria-hidden />
              Start next hand
            </button>
          ) : (
            <button
              className={`btn btn-md flex-1 ${streetClosed ? "btn-secondary" : "btn-primary"}`}
              onClick={apply}
              disabled={loading || !actionType}
            >
              <Play size={15} aria-hidden />
              Apply
              <kbd className="keycap">↵</kbd>
            </button>
          )}
          <button
            className={`btn btn-md ${streetClosed ? "btn-primary" : "btn-secondary"}`}
            onClick={advanceStreet}
            disabled={loading || complete}
          >
            {context.street === "river" ? "Showdown" : "Next street"}
            <ArrowRight size={15} aria-hidden />
            <kbd className="keycap">→</kbd>
          </button>
        </div>
      </div>

      <section className="grid gap-2 border-t border-line pt-4">
        <button
          type="button"
          className="flex items-center gap-2 text-left"
          onClick={() => setShowdownOpen((open) => !open)}
          aria-expanded={showdownOpen}
        >
          <Trophy size={15} className="text-ink-faint" aria-hidden />
          <span className="label-section">Record showdown</span>
        </button>
        {showdownOpen ? (
          <div className="grid gap-3">
            <p className="text-caption text-ink-muted">
              This is where the model finds out whether it was right. The range is scored against these cards on every
              street and the result goes into measured skill.
            </p>
            <CardPicker
              label="Villain tabled"
              count={2}
              value={villainCards}
              taken={usedCards(context)}
              onChange={setVillainCards}
              compact
            />
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex gap-1 rounded border border-line bg-surface-sunken p-0.5">
                {[
                  { label: "Hero won", value: false },
                  { label: "Villain won", value: true },
                ].map((option) => (
                  <button
                    key={option.label}
                    type="button"
                    aria-pressed={villainWon === option.value}
                    onClick={() => setVillainWon(option.value)}
                    className={`h-7 rounded-sm px-3 text-caption font-semibold transition-colors ${
                      villainWon === option.value ? "bg-accent-600 text-white" : "text-ink-muted hover:bg-surface"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <button
                className="btn btn-sm btn-primary"
                disabled={loading || villainCards.length !== 2}
                onClick={() => void onShowdown(villainCards, villainWon)}
              >
                <Check size={14} aria-hidden />
                Score this hand
              </button>
            </div>
            {villainCards.length !== 2 ? (
              <p className="text-caption text-ink-faint">Pick both of the villain's cards to score the prediction.</p>
            ) : null}
          </div>
        ) : null}
      </section>
    </div>
  );
}
