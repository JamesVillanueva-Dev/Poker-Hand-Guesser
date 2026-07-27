import { percent } from "../lib/format";
import type { PlayerProfile } from "../types/poker";

const STATS: Array<{ key: keyof PlayerProfile; label: string; sampleKey: string; detail: string }> = [
  { key: "vpip", label: "VPIP", sampleKey: "preflop_hands", detail: "Voluntarily put money in preflop, over preflop hands." },
  { key: "pfr", label: "PFR", sampleKey: "preflop_hands", detail: "Raised preflop, over preflop hands." },
  { key: "three_bet", label: "3-Bet", sampleKey: "three_bet_opportunities", detail: "Re-raised, over spots facing one raise." },
  { key: "fold_to_three_bet", label: "Fold to 3-Bet", sampleKey: "three_bets_faced", detail: "Folded, over spots facing a re-raise." },
  { key: "cbet", label: "C-Bet", sampleKey: "cbet_opportunities", detail: "Bet the flop as preflop aggressor, over those chances." },
  { key: "bluff_frequency", label: "Bluff", sampleKey: "showdown_aggressive_hands", detail: "Bet or raised then tabled a weak hand, over aggressive showdowns." },
  { key: "showdown_frequency", label: "Showdown", sampleKey: "showdowns", detail: "Reached showdown, over hands that could have." },
];

interface PlayerStatsProps {
  profile: PlayerProfile;
  samples?: Record<string, number>;
}

export function PlayerStats({ profile, samples = {} }: PlayerStatsProps) {
  return (
    <section className="panel p-4 md:p-5" aria-labelledby="stats-heading">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="stats-heading" className="label-section">
            Opponent tendencies
          </h2>
          <p className="mt-1 max-w-2xl text-body text-ink-muted">
            Each rate is a count over its own opportunities, shrunk toward a population prior. The sample size is the
            denominator it was measured over: a small one means the number is still mostly the prior.
          </p>
        </div>
        <span className="numeric text-caption text-ink-faint">{profile.hands_observed} hands observed</span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {STATS.map(({ key, label, sampleKey, detail }) => {
          const value = Number(profile[key]);
          const sample = samples[sampleKey] ?? 0;
          return (
            <div key={key} className="rounded border border-line bg-surface-raised p-3">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-caption font-medium text-ink-muted">{label}</span>
                <span className={`numeric text-micro ${sample ? "text-ink-faint" : "text-caution-700"}`}>
                  {sample ? `n=${sample}` : "prior only"}
                </span>
              </div>
              <div className="numeric mt-0.5 text-title font-semibold text-ink">{percent(value)}</div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-sunken">
                <div
                  className={`h-full rounded-full ${sample ? "bg-accent-500" : "bg-line-strong"}`}
                  style={{ width: `${Math.min(100, value * 100)}%` }}
                />
              </div>
              <p className="mt-2 text-micro leading-4 text-ink-faint">{detail}</p>
            </div>
          );
        })}

        <div className="rounded border border-line bg-surface-raised p-3">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-caption font-medium text-ink-muted">Aggression</span>
            <span className="numeric text-micro text-ink-faint">n={samples.postflop_actions ?? 0}</span>
          </div>
          <div className="numeric mt-0.5 text-title font-semibold text-ink">{profile.aggression.toFixed(2)}</div>
          <div className="numeric mt-2 text-caption text-ink-muted">River {profile.river_aggression.toFixed(2)}</div>
          <p className="mt-2 text-micro leading-4 text-ink-faint">
            Aggressive actions per passive one. Higher values widen the betting range.
          </p>
        </div>
      </div>
    </section>
  );
}
