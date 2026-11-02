export function heatLevel(count: number, target: number): number {
  if (target <= 0 || count <= 0) return 0;
  const ratio = count / target;
  if (ratio >= 1) return 5;
  if (ratio >= 0.75) return 4;
  if (ratio >= 0.5) return 3;
  if (ratio >= 0.25) return 2;
  return 1;
}
