import { Target, TrendingDown, TrendingUp } from "lucide-react";
import { bits, percent } from "../lib/format";
import type { Calibration, Street } from "../types/poker";

const STREETS: Street[] = ["preflop", "flop", "turn", "river"];

/**
 * The full accuracy view: bits better than a uniform guess, over hands the opponent
 * actually showed. When that is at or below zero it says so, in words.
 */
export function CalibrationPanel({ calibration }: { calibration: Calibration }) {
  const { overall, recent, by_street: byStreet, summary, beats_guessing: winning } = calibration;
  const scored = overall.count > 0;
  const Icon = !scored ? Target : winning ? TrendingUp : TrendingDown;
  const tone = !scored
    ? "border-line bg-surface-sunken text-ink-muted"
    : winning
      ? "border-positive-200 bg-positive-50 text-positive-700"
      : "border-caution-200 bg-caution-50 text-caution-700";

  return (
    <section className="panel overflow-hidden" aria-labelledby="calibration-heading">
      <div className={`grid gap-4 border-b p-4 md:grid-cols-[minmax(0,1fr)_auto] md:p-5 ${tone}`}>
        <div>
          <h2 id="calibration-heading" className="flex items-center gap-1.5 text-section font-semibold uppercase">
            <Icon size={14} aria-hidden />
            Measured skill
          </h2>
          <div className="numeric mt-1 text-figure-lg font-semibold text-ink">
            {scored ? bits(overall.mean_skill) : "not measured"}
          </div>
          <p className="mt-1.5 max-w-2xl text-body">{summary}</p>
          {scored && !winning ? (
            <p className="mt-1.5 max-w-2xl text-body font-medium">
              Treat the heatmap as a hypothesis, not a read, until this is above zero.
            </p>
          ) : null}
        </div>
        <dl className="grid shrink-0 grid-cols-3 gap-2 md:grid-cols-1 md:text-right">
          <div className="rounded border border-line bg-surface p-2.5">
            <dt className="text-micro uppercase text-ink-faint">Showdowns</dt>
            <dd className="numeric text-body-lg font-semibold text-ink">{overall.count}</dd>
          </div>
          <div className="rounded border border-line bg-surface p-2.5">
            <dt className="text-micro uppercase text-ink-faint">Last {calibration.recent_window}</dt>
            <dd className="numeric text-body-lg font-semibold text-ink">
              {recent.count ? bits(recent.mean_skill) : "—"}
            </dd>
          </div>
          <div className="rounded border border-line bg-surface p-2.5">
            <dt className="text-micro uppercase text-ink-faint">Top-10% hit</dt>
            <dd className="numeric text-body-lg font-semibold text-ink">
              {scored ? percent(overall.top_10_rate, 0) : "—"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="p-4 md:p-5">
        <h3 className="label-section">Where the model earns or loses its bits</h3>
        {scored ? (
          <div className="mt-3 grid gap-2 sm:grid-cols-4">
            {STREETS.map((street) => {
              const entry = byStreet[street];
              return (
                <div key={street} className="rounded border border-line bg-surface-raised p-3">
                  <div className="text-caption capitalize text-ink-muted">{street}</div>
                  <div
                    className={`numeric text-title font-semibold ${
                      !entry ? "text-ink-faint" : entry.mean_skill > 0 ? "text-positive-700" : "text-negative-700"
                    }`}
                  >
                    {entry ? bits(entry.mean_skill) : "—"}
                  </div>
                  <div className="numeric text-micro text-ink-faint">{entry ? `${entry.count} scored` : "no data"}</div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="mt-2 max-w-2xl text-body text-ink-muted">
            Record a showdown to score the range against the hand the opponent actually held. Until then every
            confidence number in this app is a prior, not a measurement, and it is labelled as one.
          </p>
        )}
        <p className="mt-3 text-caption text-ink-faint">
          Baseline is {calibration.baseline_log_loss.toFixed(2)} bits, the cost of guessing uniformly across all 169
          classes. Skill is that baseline minus the model's own loss.
        </p>
      </div>
    </section>
  );
}
