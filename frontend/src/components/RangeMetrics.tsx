import { Activity, BarChart3, Gauge, Sigma } from "lucide-react";
import type { MatrixCell, TopHand } from "../types/poker";

interface RangeMetricsProps {
  entropy: number;
  topHands: TopHand[];
  matrix: MatrixCell[];
}

function concentrationLabel(entropy: number) {
  if (entropy > 7.1) return "Wide";
  if (entropy > 6.4) return "Mixed";
  if (entropy > 5.6) return "Focused";
  return "Narrow";
}

export function RangeMetrics({ entropy, topHands, matrix }: RangeMetricsProps) {
  const topFive = topHands.slice(0, 5).reduce((sum, hand) => sum + hand.probability, 0);
  const pairMass = matrix.filter((cell) => cell.hand.length === 2).reduce((sum, cell) => sum + cell.probability, 0);
  const suitedMass = matrix.filter((cell) => cell.hand.endsWith("s")).reduce((sum, cell) => sum + cell.probability, 0);
  const total = matrix.reduce((sum, cell) => sum + cell.probability, 0);

  const cards = [
    {
      label: "Range Shape",
      value: concentrationLabel(entropy),
      detail: `Entropy ${entropy.toFixed(2)} bits`,
      icon: Gauge,
    },
    {
      label: "Top 5 Weight",
      value: `${(topFive * 100).toFixed(1)}%`,
      detail: "How much mass is on the five most likely classes",
      icon: Activity,
    },
    {
      label: "Pairs",
      value: `${(pairMass * 100).toFixed(1)}%`,
      detail: "Combined probability of AA through 22",
      icon: BarChart3,
    },
    {
      label: "Suited Hands",
      value: `${(suitedMass * 100).toFixed(1)}%`,
      detail: "Combined probability of suited non-pairs",
      icon: Sigma,
    },
  ];

  return (
    <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
      {cards.map(({ label, value, detail, icon: Icon }) => (
        <div key={label} className="metric-card">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-xs font-medium uppercase tracking-wide text-zinc-500">{label}</div>
              <div className="mono-tabular mt-1 text-2xl font-semibold text-ink">{value}</div>
            </div>
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-felt-50 text-felt-700">
              <Icon size={18} />
            </span>
          </div>
          <p className="mt-3 text-sm leading-6 text-zinc-600">{detail}</p>
        </div>
      ))}
      <div className="sr-only">Distribution total: {(total * 100).toFixed(2)} percent</div>
    </section>
  );
}
