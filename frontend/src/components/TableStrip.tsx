import { formatCard, suitOf } from "../lib/cards";
import { bb } from "../lib/format";
import type { Street } from "../types/poker";

interface TableStripProps {
  heroCards: string[];
  boardCards: string[];
  villainCards: string[];
  pot: number;
  street: Street;
  potIsOverridden: boolean;
}

function Slot({ card, hidden = false }: { card?: string; hidden?: boolean }) {
  if (hidden) {
    return (
      <span
        aria-label="Face-down card"
        className="inline-flex h-9 w-7 shrink-0 items-center justify-center rounded-sm border border-accent-700 bg-accent-600 text-white"
      >
        <span aria-hidden className="text-caption opacity-70">
          ?
        </span>
      </span>
    );
  }
  if (!card) {
    return (
      <span
        aria-label="Empty card slot"
        className="inline-flex h-9 w-7 shrink-0 items-center justify-center rounded-sm border border-dashed border-line-strong bg-surface-sunken"
      />
    );
  }
  return (
    <span
      aria-label={formatCard(card)}
      className={`inline-flex h-9 w-7 shrink-0 items-center justify-center rounded-sm border border-line-strong bg-surface text-body font-semibold ${
        suitOf(card).red ? "text-negative-600" : "text-ink"
      }`}
    >
      {formatCard(card)}
    </span>
  );
}

/**
 * A compact replacement for the 480px absolutely-positioned table graphic.
 *
 * It shows the same information — villain, board, hero, pot — in about a fifth of the
 * height, reflows to any width, and sits directly above the pickers that fill it.
 */
export function TableStrip({ heroCards, boardCards, villainCards, pot, street, potIsOverridden }: TableStripProps) {
  const revealed = villainCards.filter(Boolean).length === 2;
  const boardSize = { preflop: 0, flop: 3, turn: 4, river: 5 }[street];

  return (
    <div className="panel-sunken grid gap-2 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="label-field">Villain</span>
        <div className="flex gap-1">
          {revealed ? villainCards.map((card) => <Slot key={card} card={card} />) : [0, 1].map((index) => <Slot key={index} hidden />)}
        </div>
      </div>

      <div className="flex items-center justify-between gap-2 border-y border-line py-2">
        <div className="flex gap-1">
          {Array.from({ length: 5 }, (_, index) => (
            <Slot key={index} card={index < Math.max(boardSize, boardCards.length) ? boardCards[index] : undefined} />
          ))}
        </div>
        <div className="text-right">
          <div className="label-field">Pot</div>
          <div className="numeric text-body font-semibold text-ink">{bb(pot)}</div>
          {potIsOverridden ? <div className="text-micro text-caution-700">overridden</div> : null}
        </div>
      </div>

      <div className="flex items-center justify-between gap-2">
        <span className="label-field">Hero</span>
        <div className="flex gap-1">
          {[0, 1].map((index) => (
            <Slot key={index} card={heroCards[index]} />
          ))}
        </div>
      </div>
    </div>
  );
}
