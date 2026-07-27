export type Street = "preflop" | "flop" | "turn" | "river";
export type ActionActor = "hero" | "opponent";
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
    actor: ActionActor;
    action_type: ActionType;
    street: Street;
    position: string;
    amount: number;
    pot_before: number;
    bet_fraction_pot: number;
  };
  explanation?: string;
  board_cards?: string[];
  hero_cards?: string[];
  street?: Street;
  terminal?: boolean;
}

export interface BoardState {
  street: Street;
  board_cards: string[];
  hero_cards: string[];
  pot: number;
  effective_stack: number;
  position: string;
  hand_complete?: boolean;
}

export interface EvCandidate {
  action: string;
  sizing_pot_fraction: number;
  expected_value_bb: number;
}

export interface MoveRecommendation {
  action: string;
  sizing_bb: number;
  sizing_pot_fraction: number;
  confidence: number;
  headline: string;
  reasons: string[];
  expected_value_bb: number;
  confidence_basis: string;
  ev_breakdown: EvCandidate[];
  range_composition: Record<string, number>;
}

export interface ScoreSummary {
  count: number;
  mean_skill: number;
  mean_log_loss: number;
  top_10_rate: number;
}

export interface Calibration {
  baseline_log_loss: number;
  overall: ScoreSummary;
  by_street: Partial<Record<Street, ScoreSummary>>;
  recent: ScoreSummary;
  recent_window: number;
  summary: string;
  beats_guessing: boolean;
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
  profile: PlayerProfile;
  recommendation: MoveRecommendation;
  adaptation_notes: string[];
  hand_complete: boolean;
  profile_samples: Record<string, number>;
  calibration: Calibration;
  /**
   * What the opponent can legally do on each street, computed by the same code as the
   * policy. Keyed by street so the controls follow the user when they move ahead of the
   * action. An empty list means nothing is pending on that street.
   */
  legal_actions_by_street: Partial<Record<Street, ActionType[]>>;
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
  actor: ActionActor;
  action_type: ActionType;
  street: Street;
  position: string;
  amount: number;
  pot_before: number;
  bet_fraction_pot: number;
  board_cards: string[];
  hero_cards: string[];
  effective_stack: number;
}

export interface ShowdownPayload {
  hand_id: string;
  player_id: string;
  hole_cards: string[];
  won: boolean;
}

export interface ActionDraft {
  actor: ActionActor;
  action_type: ActionType;
  street: Street;
  position: string;
  amount: number;
  pot_before: number;
  board_cards: string[];
  hero_cards: string[];
  effective_stack: number;
}

export interface HandContext {
  street: Street;
  position: string;
  /** Pot posted before any action: blinds and antes. Everything after is derived. */
  startingPot: number;
  /** Set only when the user deliberately overrides the derived pot. */
  potOverride?: number;
  effectiveStack: number;
  heroCards: string[];
  boardCards: string[];
}
