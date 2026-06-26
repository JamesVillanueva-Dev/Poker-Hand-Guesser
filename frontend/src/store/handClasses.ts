export const ranks = ["A", "K", "Q", "J", "T", "9", "8", "7", "6", "5", "4", "3", "2"] as const;

export function handAt(row: number, col: number): string {
  const rowRank = ranks[row];
  const colRank = ranks[col];
  if (row === col) return `${rowRank}${colRank}`;
  if (row < col) return `${rowRank}${colRank}s`;
  return `${colRank}${rowRank}o`;
}

export function comboCount(hand: string): number {
  if (hand.length === 2) return 6;
  return hand.endsWith("s") ? 4 : 12;
}

export function demoRange() {
  const cells = ranks.flatMap((_, row) =>
    ranks.map((__, col) => {
      const hand = handAt(row, col);
      const base = Math.max(0.0002, 0.012 - (row + col) * 0.00055 + (hand.length === 2 ? 0.006 : 0));
      return { hand, row, col, probability: base, combo_count: comboCount(hand) };
    }),
  );
  const total = cells.reduce((sum, cell) => sum + cell.probability, 0);
  const matrix = cells.map((cell) => ({ ...cell, probability: cell.probability / total }));
  const distribution = Object.fromEntries(matrix.map((cell) => [cell.hand, cell.probability]));
  const top_hands = [...matrix].sort((a, b) => b.probability - a.probability).slice(0, 20).map(({ hand, probability }) => ({ hand, probability }));
  return { matrix, distribution, top_hands };
}
