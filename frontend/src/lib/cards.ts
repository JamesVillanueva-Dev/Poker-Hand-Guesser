/**
 * The one place cards are parsed, formatted, and reasoned about.
 *
 * There used to be a `parseCards` regex in the store and another in the hand-entry
 * component, both of which silently dropped anything they did not recognise. Parsing
 * now returns what failed so the UI can say so.
 */

export const RANKS = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;

export type Rank = (typeof RANKS)[number];
export type SuitCode = "s" | "h" | "d" | "c";

export interface Suit {
  code: SuitCode;
  glyph: string;
  name: string;
  /** Suits must be distinguishable without colour, so the glyph carries the meaning. */
  red: boolean;
}

export const SUITS: Suit[] = [
  { code: "s", glyph: "♠", name: "Spades", red: false },
  { code: "h", glyph: "♥", name: "Hearts", red: true },
  { code: "d", glyph: "♦", name: "Diamonds", red: true },
  { code: "c", glyph: "♣", name: "Clubs", red: false },
];

export const DECK: string[] = SUITS.flatMap((suit) => RANKS.map((rank) => `${rank}${suit.code}`));

export function isCard(value: string): boolean {
  return /^[AKQJT98765432][shdc]$/.test(value);
}

/** Normalise one token to `Ah` form, or return null if it is not a card. */
export function normalizeCard(token: string): string | null {
  const trimmed = token.trim();
  if (trimmed.length !== 2) return null;
  const candidate = `${trimmed[0].toUpperCase()}${trimmed[1].toLowerCase()}`;
  return isCard(candidate) ? candidate : null;
}

export interface ParseResult {
  cards: string[];
  /** Tokens that were not cards. The caller must surface these, never swallow them. */
  rejected: string[];
  duplicates: string[];
}

export function parseCardList(value: string): ParseResult {
  const cards: string[] = [];
  const rejected: string[] = [];
  const duplicates: string[] = [];

  for (const token of value.split(/[\s,]+/).filter(Boolean)) {
    const card = normalizeCard(token);
    if (!card) {
      rejected.push(token);
    } else if (cards.includes(card)) {
      duplicates.push(card);
    } else {
      cards.push(card);
    }
  }
  return { cards, rejected, duplicates };
}

export function rankOf(card: string): Rank {
  return card[0] as Rank;
}

export function suitOf(card: string): Suit {
  return SUITS.find((suit) => suit.code === card[1]) ?? SUITS[0];
}

export function formatCard(card: string): string {
  return `${rankOf(card)}${suitOf(card).glyph}`;
}

const RANK_NAMES: Record<Rank, string> = {
  A: "Ace",
  K: "King",
  Q: "Queen",
  J: "Jack",
  T: "Ten",
  "9": "Nine",
  "8": "Eight",
  "7": "Seven",
  "6": "Six",
  "5": "Five",
  "4": "Four",
  "3": "Three",
  "2": "Two",
};

/** Spoken form, for `aria-label` on card buttons and slots. "A of Clubs" is not a card. */
export function describeCard(card: string): string {
  return `${RANK_NAMES[rankOf(card)]} of ${suitOf(card).name}`;
}

/** The 169-class label for two concrete cards, matching the backend's `hand_class_of`. */
export function handClassOf(one: string, two: string): string | null {
  if (!isCard(one) || !isCard(two) || one === two) return null;
  const [high, low] = [one, two].sort((a, b) => RANKS.indexOf(rankOf(a)) - RANKS.indexOf(rankOf(b)));
  if (rankOf(high) === rankOf(low)) return `${rankOf(high)}${rankOf(low)}`;
  return `${rankOf(high)}${rankOf(low)}${suitOf(high).code === suitOf(low).code ? "s" : "o"}`;
}
