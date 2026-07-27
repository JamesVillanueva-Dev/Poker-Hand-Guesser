/**
 * The one place literal colour values live outside `index.css`.
 *
 * SVG attributes (Recharts strokes and fills) cannot take a Tailwind class, so they need
 * concrete values. Keeping them here rather than inline in components means there is
 * still exactly one file to change when the palette moves, and it mirrors the `@theme`
 * block in `index.css`.
 */
export const CHART = {
  grid: "#e3ecf5",
  axis: "#d5e2ef",
  axisText: "#5a6b80",
  reference: "#b0c4d8",
  series: ["#1d4ed8", "#3b82f6", "#60a5fa", "#047857", "#b45309"],
} as const;
