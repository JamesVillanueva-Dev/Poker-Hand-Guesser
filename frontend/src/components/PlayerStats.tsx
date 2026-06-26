import type { PlayerProfile } from "../types/poker";

const percentStats: Array<[keyof PlayerProfile, string]> = [
  ["vpip", "VPIP"],
  ["pfr", "PFR"],
  ["three_bet", "3Bet"],
  ["fold_to_three_bet", "Fold to 3Bet"],
  ["cbet", "CBet"],
  ["bluff_frequency", "Bluff"],
  ["showdown_frequency", "Showdown"],
];

const statDetails: Partial<Record<keyof PlayerProfile, string>> = {
  vpip: "How often the player voluntarily enters a pot.",
  pfr: "How often the player raises before the flop.",
  three_bet: "How often the player re-raises preflop.",
  fold_to_three_bet: "How often the player folds to a preflop re-raise.",
  cbet: "How often the player continuation bets the flop.",
  bluff_frequency: "Estimated share of aggressive actions that may be bluffs.",
  showdown_frequency: "How often observed hands reach showdown.",
};

export function PlayerStats({ profile }: { profile: PlayerProfile }) {
  return (
    <section className="card-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Player Statistics</h2>
        <span className="text-xs text-zinc-500">{profile.hands_observed} hands observed</span>
      </div>
      <p className="mb-4 text-sm leading-6 text-zinc-600">
        Profile stats change action likelihoods. A raise from a tight low-PFR player is weighted differently than a raise from a loose aggressive player.
      </p>
      <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-5">
        {percentStats.map(([key, label]) => {
          const value = Number(profile[key]);
          return (
            <div key={key} className="border border-zinc-200 p-3" style={{ borderRadius: 6 }}>
              <div className="text-xs text-zinc-500">{label}</div>
              <div className="mono-tabular mt-1 text-lg font-semibold">{(value * 100).toFixed(1)}%</div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-zinc-100">
                <div className="h-full rounded-full bg-copper" style={{ width: `${Math.min(100, value * 100)}%` }} />
              </div>
              <div className="mt-2 min-h-10 text-xs leading-5 text-zinc-500">{statDetails[key]}</div>
            </div>
          );
        })}
        <div className="border border-zinc-200 p-3" style={{ borderRadius: 6 }}>
          <div className="text-xs text-zinc-500">Aggression</div>
          <div className="mono-tabular mt-1 text-lg font-semibold">{profile.aggression.toFixed(2)}</div>
          <div className="text-xs text-zinc-500">River {profile.river_aggression.toFixed(2)}</div>
          <div className="mt-2 min-h-10 text-xs leading-5 text-zinc-500">Higher values make bets and raises more likely across a wider range.</div>
        </div>
      </div>
    </section>
  );
}
