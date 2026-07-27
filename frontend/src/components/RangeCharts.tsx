import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CHART } from "../lib/theme";
import type { TimelineEntry, TopHand } from "../types/poker";

interface RangeChartsProps {
  timeline: TimelineEntry[];
  topHands: TopHand[];
  baselineEntropy: number;
}

interface TooltipPayload {
  active?: boolean;
  label?: string | number;
  payload?: Array<{ name?: string; value?: number; color?: string }>;
}

/** A tooltip that uses the design system rather than Recharts' unstyled default. */
function ChartTooltip({ active, label, payload, unit }: TooltipPayload & { unit: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="panel px-2.5 py-2 shadow-pop">
      <div className="text-micro uppercase text-ink-faint">Action {label}</div>
      <ul className="mt-1 grid gap-0.5">
        {payload.map((entry) => (
          <li key={entry.name} className="flex items-center gap-2 text-caption">
            <span className="h-0.5 w-3 rounded-full" style={{ background: entry.color }} aria-hidden />
            <span className="text-ink-muted">{entry.name}</span>
            <span className="numeric ml-auto font-semibold text-ink">
              {Number(entry.value).toFixed(2)}
              {unit}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Both series here are real.
 *
 * This panel used to plot `aggression: 1.3 + index * 0.12` — an invented straight line
 * rendered as a filled area beside a genuine entropy series. The profile does not appear
 * in the timeline the API returns, so rather than fake a trend, these charts show only
 * what the backend actually computed per snapshot: entropy, and the probability of the
 * classes currently leading the range.
 */
export function RangeCharts({ timeline, topHands, baselineEntropy }: RangeChartsProps) {
  const tracked = topHands.slice(0, 5).map((hand) => hand.hand);
  const data = timeline.map((entry) => ({
    sequence: entry.sequence,
    entropy: Number(entry.entropy.toFixed(3)),
    ...Object.fromEntries(tracked.map((hand) => [hand, Number(((entry.distribution[hand] ?? 0) * 100).toFixed(3))])),
  }));

  const axisTick = { fontSize: 11, fill: CHART.axisText };

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <section className="panel p-4" aria-labelledby="probability-chart-heading">
        <h2 id="probability-chart-heading" className="label-section">
          Probability of the leading classes
        </h2>
        <p className="mb-3 mt-1 text-body text-ink-muted">
          How the current top hands gained or lost weight at each action.
        </p>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid strokeDasharray="2 4" stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="sequence" tick={axisTick} stroke={CHART.axis} />
              <YAxis tick={axisTick} stroke={CHART.axis} unit="%" />
              <Tooltip content={<ChartTooltip unit="%" />} cursor={{ stroke: CHART.axis }} />
              {tracked.map((hand, index) => (
                <Line
                  key={hand}
                  type="monotone"
                  dataKey={hand}
                  stroke={CHART.series[index]}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          {tracked.map((hand, index) => (
            <li key={hand} className="flex items-center gap-1.5 text-caption text-ink-muted">
              <span className="h-0.5 w-4 rounded-full" style={{ background: CHART.series[index] }} aria-hidden />
              {hand}
            </li>
          ))}
        </ul>
      </section>

      <section className="panel p-4" aria-labelledby="entropy-chart-heading">
        <h2 id="entropy-chart-heading" className="label-section">
          Range entropy
        </h2>
        <p className="mb-3 mt-1 text-body text-ink-muted">
          Bits of uncertainty about the opponent's hand. It falls as the action narrows the range.
        </p>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
              <CartesianGrid strokeDasharray="2 4" stroke={CHART.grid} vertical={false} />
              <XAxis dataKey="sequence" tick={axisTick} stroke={CHART.axis} />
              <YAxis tick={axisTick} stroke={CHART.axis} domain={[0, Math.ceil(baselineEntropy)]} unit=" b" />
              <Tooltip content={<ChartTooltip unit=" bits" />} cursor={{ stroke: CHART.axis }} />
              <ReferenceLine
                y={baselineEntropy}
                stroke={CHART.reference}
                strokeDasharray="4 4"
                label={{ value: "uniform guess", position: "insideTopRight", fontSize: 10, fill: CHART.axisText }}
              />
              <Line
                type="monotone"
                dataKey="entropy"
                stroke={CHART.series[0]}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  );
}
