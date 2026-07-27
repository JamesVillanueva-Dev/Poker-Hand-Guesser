import { AlertTriangle, PlugZap, RefreshCw, Sparkles, X } from "lucide-react";
import type { StoreError } from "../store/rangeStore";

/**
 * What the dashboard shows instead of a heatmap when there is no inference to show.
 *
 * There is deliberately no chart or grid here. The old behaviour substituted invented
 * numbers and rendered them identically to a real prediction, with a small error string
 * as the only tell. An empty screen is honest; a fabricated one is not.
 */
export function BackendOffline({ error, loading, onRetry }: { error?: StoreError; loading: boolean; onRetry: () => void }) {
  return (
    <section className="panel p-8">
      <div className="mx-auto grid max-w-xl gap-4 text-center">
        <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-surface-sunken text-ink-faint">
          <PlugZap size={22} aria-hidden />
        </span>
        <h2 className="text-title font-semibold text-ink">{loading ? "Connecting to the engine…" : "Backend offline"}</h2>
        <p className="text-body text-ink-muted">
          {loading
            ? "Waiting for the first inference."
            : "There is no range to show. This panel shows nothing rather than sample numbers: a fabricated distribution styled like a real one would be worse than no answer at all."}
        </p>
        {!loading ? (
          <div className="grid gap-3">
            {error ? (
              <p className="numeric rounded border border-line bg-surface-sunken px-3 py-2 text-left text-caption text-ink-muted">
                {error.message}
              </p>
            ) : null}
            <pre className="overflow-x-auto rounded border border-line bg-surface-sunken px-3 py-2 text-left text-caption text-ink-muted">
              python -m uvicorn backend.main:app --reload
            </pre>
            <button className="btn btn-md btn-primary mx-auto" onClick={onRetry}>
              <RefreshCw size={15} aria-hidden />
              Retry
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}

interface ErrorBannerProps {
  error: StoreError;
  onDismiss: () => void;
  onNewHand: () => void;
  onRetry: () => void;
}

/** Every error offers the action that resolves it, rather than one generic blue box. */
export function ErrorBanner({ error, onDismiss, onNewHand, onRetry }: ErrorBannerProps) {
  const action =
    error.kind === "hand-complete"
      ? { label: "Start next hand", icon: Sparkles, run: onNewHand }
      : error.kind === "offline"
        ? { label: "Retry", icon: RefreshCw, run: onRetry }
        : null;
  const tone =
    error.kind === "hand-complete"
      ? "border-accent-200 bg-accent-50 text-accent-900"
      : "border-caution-200 bg-caution-50 text-caution-700";

  return (
    <div role="alert" className={`flex flex-wrap items-center gap-3 rounded border px-4 py-3 text-body ${tone}`}>
      <AlertTriangle size={16} aria-hidden className="shrink-0" />
      <span className="min-w-0 flex-1">{error.message}</span>
      {action ? (
        <button className="btn btn-sm btn-secondary" onClick={action.run}>
          <action.icon size={14} aria-hidden />
          {action.label}
        </button>
      ) : null}
      <button className="btn btn-sm btn-ghost" onClick={onDismiss} aria-label="Dismiss">
        <X size={14} aria-hidden />
      </button>
    </div>
  );
}

/** Skeletons match the shape of the real content, so nothing shifts when it arrives. */
export function AnswerSkeleton() {
  return (
    <div className="grid gap-4" aria-hidden>
      <div className="panel h-40 animate-pulse bg-surface-sunken" />
      <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="panel h-[30rem] animate-pulse bg-surface-sunken" />
        <div className="panel h-[30rem] animate-pulse bg-surface-sunken" />
      </div>
    </div>
  );
}

const SHORTCUTS: Array<[string, string]> = [
  ["1 – 5", "Select the matching legal action"],
  ["Enter", "Apply the selected action"],
  ["→", "Advance to the next street"],
  ["←", "Step back through the timeline"],
  ["?", "Show this list"],
  ["Esc", "Close a card picker or this list"],
];

export function ShortcutOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-ink/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Keyboard shortcuts"
      onClick={onClose}
    >
      <div className="panel w-full max-w-sm p-5" onClick={(event) => event.stopPropagation()}>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="label-section">Keyboard shortcuts</h2>
          <button className="btn btn-sm btn-ghost" onClick={onClose} aria-label="Close">
            <X size={14} aria-hidden />
          </button>
        </div>
        <dl className="grid gap-2">
          {SHORTCUTS.map(([keys, description]) => (
            <div key={keys} className="flex items-center justify-between gap-3 text-body">
              <dt>
                <kbd className="rounded-sm border border-line bg-surface-sunken px-1.5 py-0.5 text-caption font-semibold text-ink">
                  {keys}
                </kbd>
              </dt>
              <dd className="text-ink-muted">{description}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
