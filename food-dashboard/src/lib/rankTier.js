/** The four rank tiers, with text-safe colours for use on paper. */
export const TIERS = [
  { max: 50, hex: "#7F1D1D", label: "Highest risk" },
  { max: 100, hex: "#C2410C", label: "High risk" },
  { max: 200, hex: "#D97706", label: "Elevated risk" },
  { max: Infinity, hex: "#B8963F", label: "Moderate risk" },
];

export const tierFor = (rank) => TIERS.find((t) => rank <= t.max);

/** Grade colours on the same severity axis: the worse, the darker. */
export const GRADE_COLORS = { A: "#C9C1B0", B: "#D97706", C: "#7F1D1D" };
