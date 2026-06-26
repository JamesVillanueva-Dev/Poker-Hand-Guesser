import type { TopHand } from "../types/poker";

export function TopHands({ hands }: { hands: TopHand[] }) {
  const max = Math.max(...hands.map((hand) => hand.probability), 0.001);

  return (
    <section className="card-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Top Hands</h2>
        <span className="text-xs text-zinc-500">Posterior</span>
      </div>
      <div className="space-y-2">
        {hands.slice(0, 12).map((hand) => (
          <div key={hand.hand} className="grid grid-cols-[42px_1fr_54px] items-center gap-3 text-sm">
            <span className="font-semibold">{hand.hand}</span>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-100">
              <div className="h-full rounded-full bg-felt-500" style={{ width: `${Math.max(3, (hand.probability / max) * 100)}%` }} />
            </div>
            <span className="mono-tabular text-right text-xs text-zinc-600">{(hand.probability * 100).toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </section>
  );
}
