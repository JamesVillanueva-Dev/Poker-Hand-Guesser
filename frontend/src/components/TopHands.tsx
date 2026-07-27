import { percent } from "../lib/format";
import { heatStyle } from "../lib/scale";
import type { MoveRecommendation, TopHand } from "../types/poker";

interface TopHandsProps {
  hands: TopHand[];
  composition: MoveRecommendation["range_composition"];
}

export function TopHands({ hands, composition }: TopHandsProps) {
  const max = Math.max(...hands.map((hand) => hand.probability), 1e-9);
  const categories = Object.entries(composition ?? {}).slice(0, 6);

  return (
    <div className="grid gap-4">
      <section className="panel p-4 md:p-5" aria-labelledby="tophands-heading">
        <h2 id="tophands-heading" className="label-section">
          Most likely holdings
        </h2>
        <p className="mt-1 text-body text-ink-muted">After the latest observed action.</p>
        <ol className="mt-4 grid gap-2">
          {hands.slice(0, 12).map((hand) => (
            <li key={hand.hand} className="grid grid-cols-[3rem_1fr_3.5rem] items-center gap-3">
              <span className="text-body font-semibold text-ink">{hand.hand}</span>
              <span className="h-2.5 overflow-hidden rounded-full bg-surface-sunken">
                <span
                  className="block h-full rounded-full"
                  style={{
                    width: `${Math.max(2, (hand.probability / max) * 100)}%`,
                    background: heatStyle(hand.probability, max).background,
                  }}
                />
              </span>
              <span className="numeric text-right text-caption text-ink-muted">{percent(hand.probability, 2)}</span>
            </li>
          ))}
        </ol>
      </section>

      {categories.length ? (
        <section className="panel p-4 md:p-5" aria-labelledby="composition-heading">
          <h2 id="composition-heading" className="label-section">
            What that range is, on this board
          </h2>
          <dl className="mt-3 grid gap-2">
            {categories.map(([category, weight]) => (
              <div key={category} className="grid grid-cols-[7rem_1fr_3rem] items-center gap-3">
                <dt className="text-caption capitalize text-ink-muted">{category}</dt>
                <dd className="h-2 overflow-hidden rounded-full bg-surface-sunken">
                  <span className="block h-full rounded-full bg-accent-500" style={{ width: `${weight * 100}%` }} />
                </dd>
                <dd className="numeric text-right text-caption text-ink-muted">{percent(weight, 0)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </div>
  );
}
