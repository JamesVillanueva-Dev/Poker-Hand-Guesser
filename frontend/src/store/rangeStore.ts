import { create } from "zustand";
import { api } from "../api/client";
import { demoRange } from "./handClasses";
import type { ActionPayload, ActionType, PlayerProfile, RangeResponse, Street } from "../types/poker";

const handId = "demo-hand-001";
const playerId = "villain-001";

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

const fallbackRange = (): RangeResponse => {
  const range = demoRange();
  return {
    hand_id: handId,
    player_id: playerId,
    ...range,
    entropy: 7.05,
    board_state: { street: "preflop", board_cards: [], pot: 0, effective_stack: 100, position: "BTN" },
    timeline: [{ sequence: 0, action_label: "Initial Range", entropy: 7.05, distribution: range.distribution }],
  };
};

interface RangeState {
  range: RangeResponse;
  profile: PlayerProfile;
  loading: boolean;
  error?: string;
  selectedSequence: number;
  start: () => Promise<void>;
  addAction: (actionType: ActionType, street: Street, betFraction: number) => Promise<void>;
  rewind: (sequence: number) => Promise<void>;
}

export const useRangeStore = create<RangeState>((set, get) => ({
  range: fallbackRange(),
  profile: fallbackProfile,
  loading: false,
  selectedSequence: 0,
  async start() {
    set({ loading: true, error: undefined });
    try {
      const range = await api.startHand(handId, playerId);
      const profile = await api.getPlayer(playerId);
      set({ range, profile, selectedSequence: range.timeline.length - 1, loading: false });
    } catch (error) {
      set({ range: fallbackRange(), profile: fallbackProfile, error: "Backend offline: showing local demo data.", loading: false });
    }
  },
  async addAction(actionType, street, betFraction) {
    const current = get().range;
    const amount = Math.round(Math.max(8, current.board_state.pot || 12) * betFraction);
    const payload: ActionPayload = {
      hand_id: current.hand_id,
      player_id: current.player_id,
      action_type: actionType,
      street,
      position: street === "preflop" ? "HJ" : "IP",
      amount,
      pot_before: Math.max(current.board_state.pot, 12),
      bet_fraction_pot: betFraction,
      board_cards: street === "preflop" ? [] : current.board_state.board_cards.length ? current.board_state.board_cards : ["As", "7d", "2c"],
      effective_stack: 100,
    };
    set({ loading: true, error: undefined });
    try {
      const range = await api.postAction(payload);
      const profile = await api.getPlayer(current.player_id);
      set({ range, profile, selectedSequence: range.timeline.length - 1, loading: false });
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
