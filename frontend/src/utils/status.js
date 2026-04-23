export function getSystemStatus(dp, eo, di) {
  if (dp > 0.2 || eo > 0.2 || di < 0.8 || di > 1.25) return "unsafe";
  if (dp > 0.1 || eo > 0.1) return "risky";
  return "safe";
}
