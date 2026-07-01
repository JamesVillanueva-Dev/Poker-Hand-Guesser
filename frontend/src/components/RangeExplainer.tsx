import { BookOpen, Info, TrendingUp } from "lucide-react";
import type { TimelineEntry, TopHand } from "../types/poker";

interface RangeExplainerProps {
  timeline: TimelineEntry[];
  topHands: TopHand[];
  entropy: number;
}

function latestChange(timeline: TimelineEntry[], hand: string) {
  if (timeline.length < 2) return 0;
  const current = timeline[timeline.length - 1].distribution[hand] ?? 0;
  const previous = timeline[timeline.length - 2].distribution[hand] ?? 0;
  return current - previous;
}

function reasonForLatest(entry?: TimelineEntry) {
  const action = entry?.action;
  if (entry?.explanation) return entry.explanation;
  if (!action) return "The first range starts close to a neutral preflop distribution weighted by real card combinations.";
  if (action.actor === "hero") return "Hero action recorded as context. The opponent range updates when the opponent acts.";
  if (["raise", "three_bet", "four_bet", "jam", "bet"].includes(action.action_type)) {
    return "Aggressive actions increase hands that the likelihood model expects to bet or raise for value, while still leaving some bluff weight.";
  }
  if (action.action_type === "call") {
    return "Calls tend to keep medium-strength and drawing hands in the range because the model expects many premiums to raise and many weak hands to fold.";
  }
  if (action.action_type === "check") {
    return "Checks usually spread probability toward hands that prefer pot control or have less incentive to build the pot.";
  }
  if (action.action_type === "fold") {
    return "Folds push probability away from strong hands because the observed action is less likely with hands that continue.";
  }
  return "The range moves by multiplying the prior probability by the estimated likelihood of this exact action.";
}

export function RangeExplainer({ timeline, topHands, entropy }: RangeExplainerProps) {
  const latest = timeline[timeline.length - 1];
  const leading = topHands.slice(0, 3).map((hand) => ({
    ...hand,
    change: latestChange(timeline, hand.hand),
  }));

  return (
    <section className="card-panel overflow-hidden">
      <div className="explain-header">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Reading The Numbers</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-zinc-600">
            Each hand class is a probability in the opponent range. After an action, the engine applies Bayesian updating:
            posterior is proportional to likelihood times prior, then renormalizes so everything sums to 100%.
          </p>
        </div>
        <BookOpen size={22} className="text-felt-700" />
      </div>
      <div className="grid gap-4 p-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-md border border-zinc-200 bg-white p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <TrendingUp size={17} className="text-copper" />
            Latest Update
          </div>
          <p className="text-sm leading-6 text-zinc-600">{reasonForLatest(latest)}</p>
          <div className="mt-4 grid gap-2">
            {leading.map((hand) => (
              <div key={hand.hand} className="grid grid-cols-[48px_1fr_72px] items-center gap-3 text-sm">
                <span className="font-semibold">{hand.hand}</span>
                <div className="h-2 overflow-hidden rounded-full bg-zinc-100">
                  <div className="h-full rounded-full bg-felt-500" style={{ width: `${Math.max(4, hand.probability * 900)}%` }} />
                </div>
                <span className={`mono-tabular text-right text-xs ${hand.change >= 0 ? "text-felt-700" : "text-red-700"}`}>
                  {hand.change >= 0 ? "+" : ""}
                  {(hand.change * 100).toFixed(2)}%
                </span>
              </div>
            ))}
          </div>
        </div>
        <div className="rounded-md border border-zinc-200 bg-[#fbfcfc] p-4">
          <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-ink">
            <Info size={17} className="text-felt-700" />
            What To Watch
          </div>
          <dl className="grid gap-3 text-sm">
            <div>
              <dt className="font-semibold text-ink">Probability</dt>
              <dd className="mt-1 leading-5 text-zinc-600">A hand's share of the current range, not a claim that the exact hand is known.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Combo Count</dt>
              <dd className="mt-1 leading-5 text-zinc-600">Pairs have 6 combos, suited hands 4, offsuit hands 12. More combos get more neutral starting weight.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Entropy</dt>
              <dd className="mt-1 leading-5 text-zinc-600">Higher entropy means a wider, less certain range. Lower entropy means the action sequence has concentrated the belief.</dd>
            </div>
            <div>
              <dt className="font-semibold text-ink">Player Stats</dt>
              <dd className="mt-1 leading-5 text-zinc-600">VPIP, PFR, aggression, and bluff frequency adjust action likelihoods, so the same bet can mean different things for different players.</dd>
            </div>
          </dl>
          <div className="mt-4 rounded-md bg-felt-50 px-3 py-2 text-xs leading-5 text-felt-700">
            Current entropy: {entropy.toFixed(2)}. Click any timeline step to inspect what the range looked like at that point.
          </div>
        </div>
      </div>
    </section>
  );
}
