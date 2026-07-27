import { ChevronDown } from "lucide-react";
import { useState } from "react";
import type { MatrixCell } from "../types/poker";

interface RangeExplainerProps {
  matrix: MatrixCell[];
  entropy: number;
  baselineEntropy: number;
}

/**
 * A disclosure, not a permanent panel.
 *
 * The combo-count entry used to state that pairs always have 6 combos, suited 4, offsuit
 * 12. That stopped being true when the engine started removing dead cards: `AA` with an
 * ace on the board has 3 live combos, and 1 if hero holds one too. It now reads the live
 * numbers off the matrix the backend actually sent.
 */
export function RangeExplainer({ matrix, entropy, baselineEntropy }: RangeExplainerProps) {
  const [open, setOpen] = useState(false);

  const blocked = matrix.filter((cell) => cell.combo_count === 0);
  const liveCombos = matrix.reduce((total, cell) => total + cell.combo_count, 0);
  const example = matrix.find((cell) => cell.hand === "AA");

  return (
    <section className="panel overflow-hidden">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 p-4 text-left"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls="explainer-body"
      >
        <span className="label-section">What do these numbers mean?</span>
        <ChevronDown size={16} className={`text-ink-faint transition-transform ${open ? "rotate-180" : ""}`} aria-hidden />
      </button>

      {open ? (
        <dl id="explainer-body" className="grid gap-4 border-t border-line p-4 md:grid-cols-2">
          <div>
            <dt className="text-body font-semibold text-ink">Probability</dt>
            <dd className="mt-1 text-body text-ink-muted">
              A hand class's share of the opponent's range right now. It is not a claim about their exact cards. After
              each action the engine multiplies the prior by how likely that action was with each holding, then
              renormalises so everything sums to 100%.
            </dd>
          </div>
          <div>
            <dt className="text-body font-semibold text-ink">Live combos</dt>
            <dd className="mt-1 text-body text-ink-muted">
              How many concrete two-card combinations of that class are still possible once the board and hero's cards
              are removed. A pair starts at 6, suited at 4, offsuit at 12, and every known card cuts into that.
              {example ? (
                <>
                  {" "}
                  Right now AA has <span className="numeric font-semibold text-ink">{example.combo_count}</span>.
                </>
              ) : null}{" "}
              {liveCombos} combos are live across all 169 classes.
            </dd>
          </div>
          <div>
            <dt className="text-body font-semibold text-ink">Impossible classes</dt>
            <dd className="mt-1 text-body text-ink-muted">
              Hatched cells have zero live combos: a known card rules every combination out. They hold exactly 0
              probability and can never recover it.
              {blocked.length ? ` ${blocked.length} class${blocked.length === 1 ? " is" : "es are"} ruled out on this board.` : " None are ruled out yet."}
            </dd>
          </div>
          <div>
            <dt className="text-body font-semibold text-ink">Entropy</dt>
            <dd className="mt-1 text-body text-ink-muted">
              Bits of uncertainty about the opponent's hand. A completely unknown range sits at{" "}
              <span className="numeric">{baselineEntropy.toFixed(2)}</span> bits; this one is at{" "}
              <span className="numeric font-semibold text-ink">{entropy.toFixed(2)}</span>. Lower means the action
              sequence has told you more.
            </dd>
          </div>
          <div className="md:col-span-2">
            <dt className="text-body font-semibold text-ink">Measured skill</dt>
            <dd className="mt-1 text-body text-ink-muted">
              How many bits better than a uniform guess the model has been on hands you recorded a showdown for. This is
              the only number here that has been checked against the truth; everything else is the model's own opinion.
            </dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
