import { X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { DECK, RANKS, SUITS, describeCard, formatCard, normalizeCard, rankOf, suitOf } from "../lib/cards";

interface CardPickerProps {
  label: string;
  /** How many slots to show. Hero and villain are 2, the board is 5. */
  count: number;
  value: string[];
  onChange: (cards: string[]) => void;
  /** Cards used elsewhere in the hand. Selecting one twice would skew the range. */
  taken?: string[];
  disabled?: boolean;
  compact?: boolean;
  hint?: string;
}

/**
 * The single card-entry control, used for hero cards, the board, and the villain's
 * showdown cards. It replaces a free-text regex field in one place and a pair of
 * rank/suit dropdowns in another.
 *
 * Typing is supported and parsed as you go, but nothing is ever dropped silently: an
 * unrecognised token is shown back to the user, and a card already used elsewhere in the
 * hand cannot be picked at all.
 */
export function CardPicker({ label, count, value, onChange, taken = [], disabled = false, compact = false, hint }: CardPickerProps) {
  const [openSlot, setOpenSlot] = useState<number | null>(null);
  const [typed, setTyped] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const gridId = useId();

  useEffect(() => {
    if (openSlot === null) return;
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) setOpenSlot(null);
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenSlot(null);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [openSlot]);

  const unavailable = new Set([...taken, ...value]);

  const assign = (slot: number, card: string) => {
    const next = [...value];
    while (next.length < slot) next.push("");
    next[slot] = card;
    onChange(next.filter(Boolean));
    setProblem(null);
    setOpenSlot(slot + 1 < count && !value[slot + 1] ? slot + 1 : null);
  };

  const clear = (slot: number) => {
    onChange(value.filter((_, index) => index !== slot));
    setProblem(null);
  };

  const commitTyped = () => {
    const token = typed.trim();
    if (!token) return;
    const card = normalizeCard(token);
    if (!card) {
      setProblem(`"${token}" is not a card. Use a rank and a suit, like Ah or Ts.`);
      return;
    }
    if (unavailable.has(card)) {
      setProblem(`${formatCard(card)} is already used in this hand.`);
      return;
    }
    if (value.length >= count) {
      setProblem(`${label} already has ${count} card${count === 1 ? "" : "s"}.`);
      return;
    }
    onChange([...value, card]);
    setTyped("");
    setProblem(null);
  };

  const slotSize = compact ? "h-11 w-8 text-body" : "h-14 w-11 text-body-lg";

  return (
    <div className="grid gap-2" ref={containerRef}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="label-field">{label}</span>
        {hint ? <span className="text-micro text-ink-faint">{hint}</span> : null}
      </div>

      <div className="relative flex flex-wrap items-center gap-1.5">
        {Array.from({ length: count }, (_, slot) => {
          const card = value[slot];
          const open = openSlot === slot;
          return (
            <div key={slot} className="relative">
              <button
                type="button"
                disabled={disabled}
                aria-label={card ? `${label} slot ${slot + 1}: ${describeCard(card)}. Change it.` : `${label} slot ${slot + 1}: empty. Choose a card.`}
                aria-expanded={open}
                aria-controls={open ? `${gridId}-grid` : undefined}
                onClick={() => setOpenSlot(open ? null : slot)}
                className={`${slotSize} inline-flex flex-col items-center justify-center rounded border font-semibold transition-colors disabled:opacity-45 ${
                  card
                    ? `border-line-strong bg-surface ${suitOf(card).red ? "text-negative-600" : "text-ink"}`
                    : "border-dashed border-line-strong bg-surface-sunken text-ink-faint"
                } ${open ? "ring-2 ring-accent-600" : ""}`}
              >
                {card ? (
                  <>
                    <span className="leading-none">{rankOf(card)}</span>
                    <span className="leading-none">{suitOf(card).glyph}</span>
                  </>
                ) : (
                  <span className="text-caption font-normal">+</span>
                )}
              </button>
              {card && !disabled ? (
                <button
                  type="button"
                  aria-label={`Remove ${describeCard(card)}`}
                  onClick={() => clear(slot)}
                  className="absolute -right-1 -top-1 inline-flex h-4 w-4 items-center justify-center rounded-full border border-line bg-surface text-ink-faint hover:border-negative-500 hover:text-negative-600"
                >
                  <X size={9} />
                </button>
              ) : null}
            </div>
          );
        })}

        {openSlot !== null ? (
          <div
            id={`${gridId}-grid`}
            role="dialog"
            aria-label={`Choose a card for ${label}`}
            className="absolute left-0 top-full z-30 mt-2 w-max rounded-md border border-line bg-surface p-2 shadow-pop"
          >
            <div className="grid gap-1">
              {SUITS.map((suit) => (
                <div key={suit.code} className="flex items-center gap-1">
                  <span
                    className={`w-4 text-center text-caption ${suit.red ? "text-negative-600" : "text-ink-muted"}`}
                    aria-hidden
                  >
                    {suit.glyph}
                  </span>
                  {RANKS.map((rank) => {
                    const card = `${rank}${suit.code}`;
                    const used = unavailable.has(card);
                    return (
                      <button
                        key={card}
                        type="button"
                        disabled={used}
                        aria-label={`${describeCard(card)}${used ? " (already used)" : ""}`}
                        onClick={() => assign(openSlot, card)}
                        className={`h-7 w-7 rounded-sm border text-caption font-semibold transition-colors ${
                          used
                            ? "cursor-not-allowed border-line bg-surface-sunken text-ink-faint line-through opacity-50"
                            : `border-line bg-surface hover:border-accent-600 hover:bg-accent-50 ${suit.red ? "text-negative-600" : "text-ink"}`
                        }`}
                      >
                        {rank}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
            <p className="mt-2 text-micro text-ink-faint">
              {DECK.length - unavailable.size} of {DECK.length} cards still available. Esc to close.
            </p>
          </div>
        ) : null}
      </div>

      {!disabled ? (
        <div className="flex items-center gap-2">
          <input
            className="field h-8 text-caption"
            value={typed}
            placeholder="or type Ah"
            aria-label={`Type a card for ${label}`}
            aria-invalid={problem !== null}
            aria-describedby={problem ? `${gridId}-problem` : undefined}
            onChange={(event) => {
              setTyped(event.target.value);
              setProblem(null);
            }}
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              commitTyped();
            }}
            onBlur={commitTyped}
          />
        </div>
      ) : null}

      {problem ? (
        <p id={`${gridId}-problem`} role="alert" className="text-caption text-negative-700">
          {problem}
        </p>
      ) : null}
    </div>
  );
}
