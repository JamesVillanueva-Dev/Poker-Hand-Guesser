export function percent(value: number, digits = 1): string {
  return `${(value * 100).toFixed(digits)}%`;
}

export function bb(value: number, digits = 1): string {
  return `${value.toFixed(digits)} bb`;
}

export function signedBb(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)} bb`;
}

export function bits(value: number, digits = 2): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)} bits`;
}

export function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
