import { ShieldQuestion, TrendingDown, TrendingUp } from "lucide-react";
import { bb, bits, percent, signedBb } from "../lib/format";
import type { Calibration, MoveRecommendation } from "../types/poker";

interface AnswerHeaderProps {
  recommendation: MoveRecommendation;
  calibration: Calibration;
  entropy: number;
}

/**
 * The answer, at the top of the reading region: what to do, what it is worth, and how
 * much the model's confidence is actually worth.
 *
 * Wrapped in an `aria-live` region because an action changes this text without moving
 * focus, and a screen-reader user would otherwise have no idea anything happened.
 */
export function AnswerHeader({ recommendation, calibration, entropy }: AnswerHeaderProps) {
  const grounded = !recommendation.confidence_basis.includes("unvalidated");
  const scored = calibration.overall.count > 0;
  const winning = calibration.beats_guessing;
  const SkillIcon = !scored ? ShieldQuestion : winning ? TrendingUp : TrendingDown;

  const skillTone = !scored
    ? "border-line bg-surface-sunken text-ink-muted"
    : winning
      ? "border-positive-200 bg-positive-50 text-positive-700"
      : "border-caution-200 bg-caution-50 text-caution-700";

  return (
    <section className="panel overflow-hidden" aria-labelledby="answer-heading">
      <div className="grid gap-4 p-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-start md:p-5">
        <div aria-live="polite">
          <h2 id="answer-heading" className="label-section">
            Recommended line
          </h2>
          <div className="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="text-figure font-semibold capitalize text-ink">{recommendation.action}</span>
            {recommendation.sizing_bb > 0 ? (
              <span className="numeric text-body-lg text-ink-muted">
                {bb(recommendation.sizing_bb)} · {percent(recommendation.sizing_pot_fraction, 0)} pot
              </span>
            ) : null}
            <span
              className={`numeric rounded-sm px-2 py-0.5 text-caption font-semibold ${
                recommendation.expected_value_bb >= 0
                  ? "bg-positive-50 text-positive-700"
                  : "bg-negative-50 text-negative-700"
              }`}
            >
              EV {signedBb(recommendation.expected_value_bb)}
            </span>
          </div>
          <p className="mt-2 max-w-2xl text-body text-ink-muted">{recommendation.headline}</p>
        </div>

        <dl className="grid grid-cols-2 gap-2 md:w-64">
          <div className={`rounded border p-2.5 ${skillTone}`}>
            <dt className="flex items-center gap-1.5 text-micro font-semibold uppercase">
              <SkillIcon size={13} aria-hidden />
              Measured skill
            </dt>
            <dd className="numeric mt-0.5 text-body-lg font-semibold">
              {scored ? bits(calibration.overall.mean_skill) : "—"}
            </dd>
            <dd className="text-micro opacity-80">
              {scored ? `${calibration.overall.count} showdowns` : "no showdowns yet"}
            </dd>
          </div>
          <div className={`rounded border p-2.5 ${grounded ? "border-line bg-surface-raised" : "border-caution-200 bg-caution-50"}`}>
            <dt className="text-micro font-semibold uppercase text-ink-faint">Confidence</dt>
            <dd className="numeric mt-0.5 text-body-lg font-semibold text-ink">
              {percent(recommendation.confidence, 0)}
            </dd>
            <dd className={`text-micro ${grounded ? "text-ink-faint" : "text-caution-700"}`}>
              {grounded ? "measured" : "unvalidated prior"}
            </dd>
          </div>
        </dl>
      </div>

      <div className="border-t border-line bg-surface-raised px-4 py-3 md:px-5">
        <ul className="grid gap-1.5 text-body text-ink-muted">
          {recommendation.reasons.slice(0, 3).map((reason) => (
            <li key={reason} className="flex gap-2">
              <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent-400" />
              {reason}
            </li>
          ))}
        </ul>
        <p className="mt-2.5 text-caption text-ink-faint">
          {recommendation.confidence_basis}. Range entropy {entropy.toFixed(2)} bits.
        </p>
      </div>
    </section>
  );
}
