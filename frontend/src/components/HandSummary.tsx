import { CircleDollarSign, Layers, Radio, UserRound } from "lucide-react";
import type { BoardState } from "../types/poker";

function CardPip({ card }: { card: string }) {
  const red = card.endsWith("h") || card.endsWith("d");
  return (
    <span className={`inline-flex h-9 w-7 items-center justify-center border bg-white text-sm font-bold shadow-sm ${red ? "text-red-600" : "text-zinc-900"}`} style={{ borderRadius: 4 }}>
      {card}
    </span>
  );
}

export function HandSummary({ board }: { board: BoardState }) {
  const cards = board.board_cards.length ? board.board_cards : ["--", "--", "--"];
  return (
    <section className="hero-panel">
      <div className="mb-6 flex flex-col justify-between gap-5 md:flex-row md:items-start">
        <div>
          <div className="text-xs font-semibold uppercase tracking-[0.18em] text-felt-700">Educational range analysis</div>
          <h1 className="mt-2 text-2xl font-semibold text-ink md:text-3xl">Real-Time Poker Range Estimator</h1>
          <p className="mt-3 max-w-4xl text-base leading-7 text-zinc-600">
            Track how observed actions reshape an opponent's likely starting hand distribution across all 169 hand classes.
          </p>
        </div>
        <span className="inline-flex w-fit items-center gap-2 rounded-full bg-white px-3 py-1.5 text-xs font-medium text-felt-700 shadow-sm ring-1 ring-felt-100">
          <Radio size={14} />
          Live inference
        </span>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="summary-tile">
          <Layers size={18} className="text-felt-700" />
          <div>
            <div className="text-xs text-zinc-500">Street</div>
            <div className="font-semibold capitalize">{board.street}</div>
          </div>
        </div>
        <div className="summary-tile block">
          <div className="mb-1 text-xs text-zinc-500">Board Cards</div>
          <div className="flex gap-1">{cards.map((card, index) => <CardPip key={`${card}-${index}`} card={card} />)}</div>
        </div>
        <div className="summary-tile">
          <CircleDollarSign size={18} className="text-copper" />
          <div>
            <div className="text-xs text-zinc-500">Pot</div>
            <div className="mono-tabular font-semibold">{board.pot.toFixed(0)} bb</div>
          </div>
        </div>
        <div className="summary-tile">
          <UserRound size={18} className="text-zinc-700" />
          <div>
            <div className="text-xs text-zinc-500">Stack / Position</div>
            <div className="font-semibold">{board.effective_stack.toFixed(0)} bb / {board.position}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
