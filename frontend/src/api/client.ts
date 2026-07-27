import type { ActionPayload, BoardState, Calibration, PlayerProfile, RangeResponse, ShowdownPayload } from "../types/poker";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export interface ShowdownResult {
  status: string;
  hole_cards: string[];
  won: boolean;
  true_class: string;
  scores: Array<{ street: string; log_loss: number; skill: number; percentile: number; top_10_hit: boolean }>;
  training_rows_written: number;
  profile: PlayerProfile;
  calibration: Calibration;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === "string") {
        message = payload.detail;
      }
    } catch {
      // Keep the HTTP status message when the response is not JSON.
    }
    throw new ApiError(response.status, response.statusText, message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  startHand(handId: string, playerId: string, boardState: BoardState, sessionProfile?: PlayerProfile): Promise<RangeResponse> {
    return request<RangeResponse>("/hand/start", {
      method: "POST",
      body: JSON.stringify({
        hand_id: handId,
        player_id: playerId,
        board_state: boardState,
        session_profile: sessionProfile,
      }),
    });
  },
  postAction(payload: ActionPayload): Promise<RangeResponse> {
    return request<RangeResponse>("/action", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  postShowdown(payload: ShowdownPayload): Promise<ShowdownResult> {
    return request<ShowdownResult>("/showdown", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  getRange(handId: string): Promise<RangeResponse> {
    return request<RangeResponse>(`/range/${handId}`);
  },
  getCalibration(): Promise<Calibration> {
    return request<Calibration>("/calibration");
  },
  rewind(handId: string, sequence: number): Promise<RangeResponse> {
    return request<RangeResponse>(`/range/${handId}/snapshot/${sequence}`);
  },
  getPlayer(playerId: string): Promise<PlayerProfile> {
    return request<PlayerProfile>(`/player/${playerId}`);
  },
};
