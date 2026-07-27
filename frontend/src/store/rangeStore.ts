import { create } from "zustand";
import { ApiError, api } from "../api/client";
import type { ActionDraft, ActionPayload, ActionType, BoardState, HandContext, PlayerProfile, RangeResponse } from "../types/poker";

const playerId = "villain-001";

const initialContext: HandContext = {
  street: "preflop",
  position: "BTN",
  startingPot: 1.5,
  effectiveStack: 100,
  heroCards: [],
  boardCards: [],
};

// Sent to the backend as the starting profile for a fresh session. These are population
// priors, not a read: the backend replaces every rate with a measured one as soon as it
// has the counts to derive it from.
const startingProfile: PlayerProfile = {
  player_id: playerId,
  vpip: 0.24,
  pfr: 0.16,
  three_bet: 0.07,
  fold_to_three_bet: 0.47,
  cbet: 0.55,
  aggression: 1.7,
  river_aggression: 1.2,
  bluff_frequency: 0.22,
  showdown_frequency: 0.28,
  hands_observed: 0,
};

const boardFromContext = (context: HandContext): BoardState => ({
  street: context.street,
  board_cards: context.boardCards,
  hero_cards: context.heroCards.slice(0, 2),
  pot: context.startingPot,
  effective_stack: context.effectiveStack,
  position: context.position,
});

const contextFromRange = (range: RangeResponse, previous: HandContext): HandContext => ({
  ...previous,
  street: range.board_state.street,
  position: range.board_state.position,
  effectiveStack: range.board_state.effective_stack || previous.effectiveStack,
  heroCards: range.board_state.hero_cards,
  boardCards: range.board_state.board_cards,
  potOverride: undefined,
});

export type ErrorKind = "offline" | "hand-complete" | "validation" | "unknown";

export interface StoreError {
  kind: ErrorKind;
  message: string;
}

interface RangeState {
  range: RangeResponse | null;
  profile: PlayerProfile;
  handContext: HandContext;
  handNumber: number;
  loading: boolean;
  error?: StoreError;
  selectedSequence: number;
  updateContext: (context: Partial<HandContext>) => void;
  dismissError: () => void;
  newHand: (keepProfile?: boolean) => Promise<void>;
  resetSession: () => Promise<void>;
  addAction: (draft: ActionDraft) => Promise<void>;
  recordShowdown: (holeCards: string[], won: boolean) => Promise<void>;
  rewind: (sequence: number) => Promise<void>;
}

export const useRangeStore = create<RangeState>((set, get) => ({
  range: null,
  profile: startingProfile,
  handContext: initialContext,
  handNumber: 1,
  loading: false,
  selectedSequence: 0,
  updateContext(context) {
    set((state) => ({ handContext: { ...state.handContext, ...context } }));
  },
  dismissError() {
    set({ error: undefined });
  },
  async newHand(keepProfile = true) {
    const state = get();
    const nextHandNumber = keepProfile ? state.handNumber + 1 : 1;
    const handId = `session-hand-${Date.now()}-${nextHandNumber}`;
    // A new hand keeps the table setup but never the cards or the board.
    const context: HandContext = keepProfile
      ? { ...state.handContext, street: "preflop", heroCards: [], boardCards: [], potOverride: undefined }
      : initialContext;
    const profile = keepProfile ? state.profile : startingProfile;
    set({ loading: true, error: undefined });
    try {
      const range = await api.startHand(handId, playerId, boardFromContext(context), profile);
      set({
        range,
        profile: range.profile,
        handContext: contextFromRange(range, context),
        handNumber: nextHandNumber,
        selectedSequence: range.timeline.length - 1,
        loading: false,
      });
    } catch (error) {
      // No range is better than an invented one. The dashboard renders a disconnected
      // panel rather than a heatmap that looks like a real prediction.
      set({
        range: null,
        profile,
        handContext: context,
        handNumber: nextHandNumber,
        error: describe(error),
        loading: false,
      });
    }
  },
  async resetSession() {
    set({ profile: startingProfile, handContext: initialContext, handNumber: 0 });
    await get().newHand(false);
  },
  async addAction(draft) {
    const current = get().range;
    if (!current) {
      await get().newHand(true);
      return;
    }
    const context = get().handContext;
    const payload: ActionPayload = {
      hand_id: current.hand_id,
      player_id: current.player_id,
      actor: draft.actor,
      action_type: draft.action_type,
      street: draft.street,
      position: draft.position,
      amount: draft.amount,
      pot_before: draft.pot_before,
      bet_fraction_pot: draft.pot_before > 0 ? draft.amount / draft.pot_before : 0,
      board_cards: context.boardCards,
      hero_cards: context.heroCards.slice(0, 2),
      effective_stack: context.effectiveStack,
    };
    set({ loading: true, error: undefined });
    const apply = (range: RangeResponse) =>
      set({
        range,
        profile: range.profile,
        handContext: contextFromRange(range, get().handContext),
        selectedSequence: range.timeline.length - 1,
        loading: false,
      });
    try {
      apply(await api.postAction(payload));
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        try {
          await api.startHand(current.hand_id, current.player_id, boardFromContext(context), get().profile);
          apply(await api.postAction(payload));
          return;
        } catch (retryError) {
          set({ error: describe(retryError), loading: false });
          return;
        }
      }
      set({ error: describe(error), loading: false });
    }
  },
  async recordShowdown(holeCards, won) {
    const current = get().range;
    if (!current) return;
    set({ loading: true, error: undefined });
    try {
      await api.postShowdown({
        hand_id: current.hand_id,
        player_id: current.player_id,
        hole_cards: holeCards,
        won,
      });
      // The showdown is where the model finds out whether it was right. Pull the hand
      // back so the dashboard shows the updated calibration straight away.
      const range = await api.getRange(current.hand_id);
      set({ range, profile: range.profile, loading: false });
    } catch (error) {
      set({ error: describe(error), loading: false });
    }
  },
  async rewind(sequence) {
    const current = get().range;
    if (!current) return;
    set({ loading: true, error: undefined });
    try {
      const range = await api.rewind(current.hand_id, sequence);
      set({ range, selectedSequence: sequence, loading: false });
    } catch (error) {
      set({ error: describe(error), loading: false });
    }
  },
}));

function describe(error: unknown): StoreError {
  if (error instanceof ApiError) {
    if (error.status === 409) return { kind: "hand-complete", message: error.message };
    if (error.status === 422) return { kind: "validation", message: error.message };
    return { kind: "unknown", message: error.message };
  }
  return { kind: "offline", message: "Backend offline. Start FastAPI on port 8000 to run live inference." };
}

/**
 * The pot going into the next action.
 *
 * Derived, never typed: the backend already maintains a running pot across the hand, so
 * asking the user to retype it every street only creates a way to feed the policy a
 * wrong `bet_fraction_pot`. An explicit override exists for reconstructing a hand
 * mid-stream, and it has to be chosen deliberately.
 */
export function derivedPot(range: RangeResponse | null, context: HandContext): number {
  if (context.potOverride !== undefined) return context.potOverride;
  if (!range) return context.startingPot;
  return range.board_state.pot || context.startingPot;
}

/** Every card the hand already knows about, so no card can be chosen twice. */
export function usedCards(context: HandContext, extra: string[] = []): string[] {
  return [...context.heroCards, ...context.boardCards, ...extra].filter(Boolean);
}

/** How many board cards the given street should show. */
export function boardSizeFor(street: HandContext["street"]): number {
  return { preflop: 0, flop: 3, turn: 4, river: 5 }[street];
}

export const ACTION_LABELS: Record<ActionType, string> = {
  fold: "Fold",
  check: "Check",
  call: "Call",
  bet: "Bet",
  raise: "Raise",
  three_bet: "3-Bet",
  four_bet: "4-Bet",
  jam: "Jam",
};

/** Actions that need a size. The rest send 0 and hide the sizing controls. */
export const SIZED_ACTIONS: ActionType[] = ["call", "bet", "raise", "three_bet", "four_bet", "jam"];
