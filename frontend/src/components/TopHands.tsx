import type { TopHand } from "../types/poker";

export function TopHands({ hands }: { hands: TopHand[] }) {
  const max = Math.max(...hands.map((hand) => hand.probability), 0.001);

  return (
    <section className="card-panel p-5 md:p-6">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Top Hands</h2>
        <span className="text-xs text-zinc-500">Posterior</span>
      </div>
      <p className="mb-5 text-base leading-7 text-zinc-600">
        These are the hand classes with the most probability after the latest observed action.
      </p>
      <div className="space-y-3">
        {hands.slice(0, 14).map((hand) => (
          <div key={hand.hand} className="grid grid-cols-[52px_1fr_68px] items-center gap-4 text-sm">
            <span className="text-base font-semibold">{hand.hand}</span>
            <div className="h-3 overflow-hidden rounded-full bg-zinc-100">
              <div className="h-full rounded-full bg-felt-500" style={{ width: `${Math.max(3, (hand.probability / max) * 100)}%` }} />
            </div>
            <span className="mono-tabular text-right text-sm text-zinc-600">{(hand.probability * 100).toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </section>
  );
}
