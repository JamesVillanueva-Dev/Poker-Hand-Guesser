export type Street = "preflop" | "flop" | "turn" | "river";
export type ActionType = "fold" | "check" | "call" | "bet" | "raise" | "three_bet" | "four_bet" | "jam";

export interface MatrixCell {
  hand: string;
  row: number;
  col: number;
  probability: number;
  combo_count: number;
}

export interface TopHand {
  hand: string;
  probability: number;
}

export interface TimelineEntry {
  sequence: number;
  action_label: string;
  entropy: number;
  distribution: Record<string, number>;
  action?: {
    player_id: string;
    action_type: ActionType;
    street: Street;
    position: string;
    amount: number;
    pot_before: number;
    bet_fraction_pot: number;
  };
}

export interface BoardState {
  street: Street;
  board_cards: string[];
  pot: number;
  effective_stack: number;
  position: string;
}

export interface RangeResponse {
  hand_id: string;
  player_id: string;
  distribution: Record<string, number>;
  top_hands: TopHand[];
  matrix: MatrixCell[];
  entropy: number;
  timeline: TimelineEntry[];
  board_state: BoardState;
}

export interface PlayerProfile {
  player_id: string;
  vpip: number;
  pfr: number;
  three_bet: number;
  fold_to_three_bet: number;
  cbet: number;
  aggression: number;
  river_aggression: number;
  bluff_frequency: number;
  showdown_frequency: number;
  hands_observed: number;
}

export interface ActionPayload {
  hand_id: string;
  player_id: string;
  action_type: ActionType;
  street: Street;
  position: string;
  amount: number;
  pot_before: number;
  bet_fraction_pot: number;
  board_cards: string[];
  effective_stack: number;
}
