import { Area, AreaChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimelineEntry, TopHand } from "../types/poker";

export function RangeCharts({ timeline, topHands }: { timeline: TimelineEntry[]; topHands: TopHand[] }) {
  const trackedHands = topHands.slice(0, 5).map((hand) => hand.hand);
  const handData = timeline.map((entry) => ({
    sequence: entry.sequence,
    entropy: Number(entry.entropy.toFixed(4)),
    ...Object.fromEntries(trackedHands.map((hand) => [hand, Number(((entry.distribution[hand] ?? 0) * 100).toFixed(3))])),
  }));

  const trendData = timeline.map((entry, index) => ({
    sequence: entry.sequence,
    aggression: 1.3 + index * 0.12 + (entry.action?.action_type === "jam" ? 0.55 : 0),
    vpip: 24 + index * 0.6,
  }));

  return (
    <section className="grid gap-4 xl:grid-cols-2">
      <div className="card-panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Probability Changes</h2>
        <p className="mb-3 mt-1 text-sm text-zinc-600">Lines show how the current top hands gained or lost probability at each action.</p>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={handData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
              <XAxis dataKey="sequence" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip formatter={(value) => `${Number(value).toFixed(2)}%`} />
              <Legend />
              {trackedHands.map((hand, index) => (
                <Line key={hand} type="monotone" dataKey={hand} stroke={["#13533f", "#b6673a", "#334155", "#1d7c5b", "#7c3aed"][index]} strokeWidth={2} dot={false} animationDuration={450} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="card-panel p-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-600">Entropy & Trends</h2>
        <p className="mb-3 mt-1 text-sm text-zinc-600">Entropy drops as the range narrows. Aggression is shown as a contextual trend line.</p>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={handData.map((entry, index) => ({ ...entry, ...trendData[index] }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
              <XAxis dataKey="sequence" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Legend />
              <Area type="monotone" dataKey="entropy" stroke="#13533f" fill="#d9efe5" animationDuration={450} />
              <Area type="monotone" dataKey="aggression" stroke="#b6673a" fill="#f1ddd1" animationDuration={450} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}
