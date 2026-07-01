import { create } from "zustand";
import { api } from "../api/client";
import { demoRange } from "./handClasses";
import type { ActionDraft, ActionPayload, BoardState, HandContext, PlayerProfile, RangeResponse } from "../types/poker";

const playerId = "villain-001";
const initialContext: HandContext = {
  street: "preflop",
  position: "BTN",
  pot: 1.5,
  effectiveStack: 100,
  heroCards: "",
  boardCards: "",
};

const fallbackProfile: PlayerProfile = {
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
  board_cards: parseCards(context.boardCards),
  hero_cards: parseCards(context.heroCards).slice(0, 2),
  pot: context.pot,
  effective_stack: context.effectiveStack,
  position: context.position,
});

const fallbackRange = (handId = "demo-hand-001", profile = fallbackProfile, context = initialContext): RangeResponse => {
  const range = demoRange();
  return {
    hand_id: handId,
    player_id: playerId,
    ...range,
    entropy: 7.05,
    board_state: boardFromContext(context),
    timeline: [{ sequence: 0, action_label: "Initial Range", entropy: 7.05, distribution: range.distribution }],
    profile,
    adaptation_notes: [
      "Session-only model: waiting for live backend actions before adapting.",
      "Start FastAPI to enable live recommendations and profile updates.",
    ],
    recommendation: {
      action: "check",
      sizing_bb: 0,
      sizing_pot_fraction: 0,
      confidence: 0.4,
      headline: "Backend offline.",
      reasons: ["Live strategy recommendations require the FastAPI backend."],
    },
  };
};

interface RangeState {
  range: RangeResponse;
  profile: PlayerProfile;
  handContext: HandContext;
  handNumber: number;
  loading: boolean;
  error?: string;
  selectedSequence: number;
  updateContext: (context: Partial<HandContext>) => void;
  newHand: (keepProfile?: boolean) => Promise<void>;
  resetSession: () => Promise<void>;
  addAction: (draft: ActionDraft) => Promise<void>;
  rewind: (sequence: number) => Promise<void>;
}

export const useRangeStore = create<RangeState>((set, get) => ({
  range: fallbackRange(),
  profile: fallbackProfile,
  handContext: initialContext,
  handNumber: 1,
  loading: false,
  selectedSequence: 0,
  updateContext(context) {
    set((state) => ({ handContext: { ...state.handContext, ...context } }));
  },
  async newHand(keepProfile = true) {
    const state = get();
    const nextHandNumber = keepProfile ? state.handNumber + 1 : 1;
    const handId = `session-hand-${Date.now()}-${nextHandNumber}`;
    const context = keepProfile ? state.handContext : initialContext;
    const profile = keepProfile ? state.profile : fallbackProfile;
    set({ loading: true, error: undefined });
    try {
      const range = await api.startHand(handId, playerId, boardFromContext(context), profile);
      set({
        range,
        profile: range.profile,
        handContext: {
          ...context,
          street: range.board_state.street,
          pot: range.board_state.pot,
          effectiveStack: range.board_state.effective_stack,
          position: range.board_state.position,
          boardCards: range.board_state.board_cards.join(" "),
          heroCards: range.board_state.hero_cards.join(" "),
        },
        handNumber: nextHandNumber,
        selectedSequence: range.timeline.length - 1,
        loading: false,
      });
    } catch (error) {
      set({ range: fallbackRange(handId, profile, context), profile, error: "Backend offline: showing local demo data.", loading: false });
    }
  },
  async resetSession() {
    set({ profile: fallbackProfile, handContext: initialContext, handNumber: 0 });
    await get().newHand(false);
  },
  async addAction(draft) {
    const current = get().range;
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
      board_cards: draft.board_cards,
      hero_cards: draft.hero_cards,
      effective_stack: draft.effective_stack,
    };
    set({ loading: true, error: undefined });
    try {
      const range = await api.postAction(payload);
      set({
        range,
        profile: range.profile,
        handContext: {
          street: range.board_state.street,
          position: range.board_state.position,
          pot: range.board_state.pot,
          effectiveStack: range.board_state.effective_stack,
          heroCards: range.board_state.hero_cards.join(" "),
          boardCards: range.board_state.board_cards.join(" "),
        },
        selectedSequence: range.timeline.length - 1,
        loading: false,
      });
    } catch (error) {
      set({ error: "Could not reach backend. Start FastAPI to run live inference.", loading: false });
    }
  },
  async rewind(sequence) {
    const current = get().range;
    set({ loading: true, error: undefined });
    try {
      const range = await api.rewind(current.hand_id, sequence);
      set({ range, selectedSequence: sequence, loading: false });
    } catch (error) {
      const snapshot = current.timeline[sequence];
      if (!snapshot) {
        set({ loading: false, error: "Snapshot unavailable." });
        return;
      }
      const demo = demoRange();
      const matrix = demo.matrix.map((cell) => ({ ...cell, probability: snapshot.distribution[cell.hand] ?? cell.probability }));
      const top_hands = [...matrix].sort((a, b) => b.probability - a.probability).slice(0, 20).map(({ hand, probability }) => ({ hand, probability }));
      set({ range: { ...current, distribution: snapshot.distribution, matrix, top_hands, entropy: snapshot.entropy }, selectedSequence: sequence, loading: false });
    }
  },
}));

function parseCards(value: string): string[] {
  return value
    .split(/[\s,]+/)
    .map((card) => card.trim())
    .filter(Boolean)
    .map((card) => `${card[0]?.toUpperCase() ?? ""}${card[1]?.toLowerCase() ?? ""}`)
    .filter((card) => /^[AKQJT98765432][shdc]$/.test(card));
}
