// Mirrors the web dashboard's palette so screenshots from either surface look
// like the same product.
export const colors = {
  bg: "#020617",
  surface: "#0f172a",
  surfaceAlt: "#1e293b",
  border: "#334155",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textFaint: "#64748b",
  accent: "#f97316",
};

// YlOrRd-derived, colorblind-safe: red (most dangerous) → yellow (least).
export const RISK_TIERS = [
  { max: 50, color: "#ef4444", label: "Highest risk" },
  { max: 100, color: "#f97316", label: "High risk" },
  { max: 200, color: "#fbbf24", label: "Elevated risk" },
  { max: Infinity, color: "#fde68a", label: "Moderate risk" },
];

export function riskTier(rank) {
  return RISK_TIERS.find((t) => rank <= t.max);
}

export const riskColor = (rank) => riskTier(rank).color;
export const riskLabel = (rank) => riskTier(rank).label;
