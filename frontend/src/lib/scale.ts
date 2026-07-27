/**
 * The heatmap colour ramp.
 *
 * The old ramp swept one hue while moving lightness and saturation together, which
 * compressed the middle of the distribution into indistinguishable mush. This is a
 * monotonic-lightness sequential ramp (ColorBrewer Blues, extended at both ends): safe
 * under deuteranopia and protanopia because it never relies on a red/green distinction,
 * and legible at 40px because adjacent steps differ in lightness, not just hue.
 */

const RAMP: Array<[number, number, number]> = [
  [247, 251, 255],
  [214, 232, 248],
  [172, 209, 240],
  [120, 178, 225],
  [66, 141, 201],
  [28, 96, 163],
  [10, 52, 110],
];

/** Range distributions are heavy-tailed, so a linear map leaves 150 cells identical. */
const GAMMA = 0.55;

function interpolate(intensity: number): [number, number, number] {
  const clamped = Math.min(1, Math.max(0, intensity));
  const scaled = clamped * (RAMP.length - 1);
  const index = Math.min(RAMP.length - 2, Math.floor(scaled));
  const t = scaled - index;
  const from = RAMP[index];
  const to = RAMP[index + 1];
  return [
    Math.round(from[0] + (to[0] - from[0]) * t),
    Math.round(from[1] + (to[1] - from[1]) * t),
    Math.round(from[2] + (to[2] - from[2]) * t),
  ];
}

export interface HeatStyle {
  background: string;
  color: string;
}

export function heatStyle(probability: number, max: number): HeatStyle {
  const intensity = max > 0 ? Math.pow(Math.min(1, probability / max), GAMMA) : 0;
  const [r, g, b] = interpolate(intensity);
  // Flip the label to white once the fill is dark enough that ink would fail contrast.
  return { background: `rgb(${r} ${g} ${b})`, color: intensity > 0.62 ? "#ffffff" : "#0f1c2e" };
}

/** Evenly spaced swatches for the legend, so colour maps to a number the user can read. */
export function legendStops(max: number, steps = 5): Array<{ background: string; probability: number }> {
  return Array.from({ length: steps }, (_, index) => {
    const probability = (max * index) / (steps - 1);
    return { background: heatStyle(probability, max).background, probability };
  });
}
