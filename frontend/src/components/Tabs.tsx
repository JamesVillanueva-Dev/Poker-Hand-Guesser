import { useId, useRef, type ReactNode } from "react";

export interface TabDefinition {
  id: string;
  label: string;
  content: ReactNode;
}

interface TabsProps {
  tabs: TabDefinition[];
  active: string;
  onChange: (id: string) => void;
  label: string;
}

/** Roving-focus tablist. Arrow keys move between tabs, as the pattern requires. */
export function Tabs({ tabs, active, onChange, label }: TabsProps) {
  const baseId = useId();
  const listRef = useRef<HTMLDivElement>(null);

  const move = (offset: number) => {
    const index = tabs.findIndex((tab) => tab.id === active);
    const next = tabs[(index + offset + tabs.length) % tabs.length];
    onChange(next.id);
    listRef.current?.querySelector<HTMLButtonElement>(`#${CSS.escape(`${baseId}-${next.id}`)}`)?.focus();
  };

  return (
    <div className="grid gap-3">
      <div
        ref={listRef}
        role="tablist"
        aria-label={label}
        className="flex flex-wrap gap-1 rounded border border-line bg-surface-sunken p-1"
        onKeyDown={(event) => {
          if (event.key === "ArrowRight") {
            event.preventDefault();
            move(1);
          }
          if (event.key === "ArrowLeft") {
            event.preventDefault();
            move(-1);
          }
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`${baseId}-${tab.id}`}
            role="tab"
            type="button"
            aria-selected={active === tab.id}
            aria-controls={`${baseId}-${tab.id}-panel`}
            tabIndex={active === tab.id ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={`h-8 rounded-sm px-3 text-caption font-semibold transition-colors ${
              active === tab.id ? "bg-surface text-ink shadow-panel" : "text-ink-muted hover:text-ink"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab) =>
        tab.id === active ? (
          <div
            key={tab.id}
            id={`${baseId}-${tab.id}-panel`}
            role="tabpanel"
            aria-labelledby={`${baseId}-${tab.id}`}
            tabIndex={0}
          >
            {tab.content}
          </div>
        ) : null,
      )}
    </div>
  );
}
