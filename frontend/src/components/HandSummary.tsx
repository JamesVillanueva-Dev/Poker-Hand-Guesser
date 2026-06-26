import { CircleDollarSign, Layers, Radio, UserRound } from "lucide-react";
import type { BoardState } from "../types/poker";

function CardPip({ card }: { card: string }) {
  const red = card.endsWith("h") || card.endsWith("d");
  return (
    <span className={`inline-flex h-9 w-7 items-center justify-center border bg-white text-sm font-bold ${red ? "text-red-600" : "text-zinc-900"}`} style={{ borderRadius: 4 }}>
      {card}
    </span>
  );
}

export function HandSummary({ board }: { board: BoardState }) {
  const cards = board.board_cards.length ? board.board_cards : ["--", "--", "--"];
  return (
    <section className="card-panel p-4">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-ink">Real-Time Range Estimator</h1>
        <span className="inline-flex items-center gap-2 rounded-full bg-felt-50 px-3 py-1 text-xs font-medium text-felt-700">
          <Radio size={14} />
          Live inference
        </span>
      </div>
      <div className="grid gap-3 sm:grid-cols-4">
        <div className="flex items-center gap-3 border border-zinc-200 p-3" style={{ borderRadius: 6 }}>
          <Layers size={18} className="text-felt-700" />
          <div>
            <div className="text-xs text-zinc-500">Street</div>
            <div className="font-semibold capitalize">{board.street}</div>
          </div>
        </div>
        <div className="border border-zinc-200 p-3" style={{ borderRadius: 6 }}>
          <div className="mb-1 text-xs text-zinc-500">Board Cards</div>
          <div className="flex gap-1">{cards.map((card, index) => <CardPip key={`${card}-${index}`} card={card} />)}</div>
        </div>
        <div className="flex items-center gap-3 border border-zinc-200 p-3" style={{ borderRadius: 6 }}>
          <CircleDollarSign size={18} className="text-copper" />
          <div>
            <div className="text-xs text-zinc-500">Pot</div>
            <div className="mono-tabular font-semibold">{board.pot.toFixed(0)} bb</div>
          </div>
        </div>
        <div className="flex items-center gap-3 border border-zinc-200 p-3" style={{ borderRadius: 6 }}>
          <UserRound size={18} className="text-zinc-700" />
          <div>
            <div className="text-xs text-zinc-500">Stack / Position</div>
            <div className="font-semibold">{board.effective_stack.toFixed(0)} bb · {board.position}</div>
          </div>
        </div>
      </div>
    </section>
  );
}
