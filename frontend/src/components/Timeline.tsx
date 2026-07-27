import { percent } from "../lib/format";
import type { TimelineEntry } from "../types/poker";

interface TimelineProps {
  entries: TimelineEntry[];
  selected: number;
  onSelect: (sequence: number) => void;
}

/**
 * The rewind scrubber.
 *
 * Rewind is the best thing in this app and used to be a horizontal strip of cards whose
 * only affordance was a `title` tooltip. It now reads as a track you can move along, with
 * the entropy of each step drawn on it so you can see where the range collapsed.
 */
export function Timeline({ entries, selected, onSelect }: TimelineProps) {
  if (!entries.length) return null;
  const maxEntropy = Math.max(...entries.map((entry) => entry.entropy), 1e-9);
  const current = entries.find((entry) => entry.sequence === selected) ?? entries[entries.length - 1];
  const atLatest = selected === entries[entries.length - 1].sequence;

  return (
    <section className="panel p-4 md:p-5" aria-labelledby="timeline-heading">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 id="timeline-heading" className="label-section">
            Rewind
          </h2>
          <p className="mt-1 text-body text-ink-muted">
            Step back through the hand to see what the range looked like at each action.
          </p>
        </div>
        {!atLatest ? (
          <button className="btn btn-sm btn-secondary" onClick={() => onSelect(entries[entries.length - 1].sequence)}>
            Back to latest
          </button>
        ) : null}
      </div>

      <ol
        className="flex items-end gap-1"
        role="listbox"
        aria-label="Hand timeline"
        aria-activedescendant={`step-${current.sequence}`}
      >
        {/* With one snapshot there is nothing to scrub between; the bars are sized so a
            single step reads as a marker rather than a full-width block. */}
        {entries.map((entry) => {
          const active = entry.sequence === selected;
          const height = Math.max(8, (entry.entropy / maxEntropy) * 56);
          return (
            <li key={entry.sequence} className="flex min-w-0 max-w-24 flex-1 flex-col items-center gap-1">
              <span className="numeric text-micro text-ink-faint">{entry.entropy.toFixed(1)}</span>
              <button
                id={`step-${entry.sequence}`}
                type="button"
                role="option"
                aria-selected={active}
                aria-label={`${entry.action_label}. Entropy ${entry.entropy.toFixed(2)} bits.`}
                onClick={() => onSelect(entry.sequence)}
                className={`w-full rounded-sm transition-colors ${
                  active ? "bg-accent-600" : "bg-accent-200 hover:bg-accent-400"
                }`}
                style={{ height }}
              />
              <span className="w-full truncate text-center text-micro text-ink-faint" aria-hidden>
                {entry.sequence}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="mt-3 rounded border border-line bg-surface-raised p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <span className="text-body font-semibold text-ink">{current.action_label}</span>
          <span className="numeric text-caption text-ink-muted">
            entropy {current.entropy.toFixed(2)} bits
            {current.action ? ` · ${percent(current.action.bet_fraction_pot, 0)} pot` : ""}
          </span>
        </div>
        {current.explanation ? <p className="mt-1.5 text-body text-ink-muted">{current.explanation}</p> : null}
      </div>
    </section>
  );
}
