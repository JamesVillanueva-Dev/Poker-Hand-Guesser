import type { ActionPayload, BoardState, PlayerProfile, RangeResponse } from "../types/poker";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
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
  rewind(handId: string, sequence: number): Promise<RangeResponse> {
    return request<RangeResponse>(`/range/${handId}/snapshot/${sequence}`);
  },
  getPlayer(playerId: string): Promise<PlayerProfile> {
    return request<PlayerProfile>(`/player/${playerId}`);
  },
};
