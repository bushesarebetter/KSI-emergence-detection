import { useState } from "react";

const RUN_CHIPS = [
  { label: "Train", value: "2016–2024" },
  { label: "Predict", value: "2025–2027" },
  { label: "Mode", value: "Forward run" },
];

export default function Header() {
  const [modalOpen, setModalOpen] = useState(false);

  return (
    <>
      <header className="h-12 bg-slate-950 border-b border-slate-800 flex items-center px-5 justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-orange-500 shadow-[0_0_6px_#f97316]" />
          <span className="text-slate-100 text-sm font-semibold tracking-tight">KSI Emergence</span>
          <span className="text-slate-700 select-none">·</span>
          <span className="text-slate-500 text-xs hidden sm:block">San Diego</span>
        </div>

        <div className="flex items-center gap-2">
          {RUN_CHIPS.map(({ label, value }) => (
            <span
              key={label}
              className="hidden md:flex items-center gap-1.5 bg-slate-800 border border-slate-700/60 text-xs px-2.5 py-1 rounded-md"
            >
              <span className="text-slate-500 font-medium">{label}</span>
              <span className="text-slate-300">{value}</span>
            </span>
          ))}

          <button
            onClick={() => setModalOpen(true)}
            className="flex items-center gap-1.5 text-xs bg-slate-800 border border-slate-700 hover:border-orange-500/50 hover:text-orange-400 text-slate-400 px-3 py-1.5 rounded-md transition-colors"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="shrink-0">
              <circle cx="6" cy="6" r="5.5" stroke="currentColor" />
              <path d="M6 5.5v3M6 3.5h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            Methodology
          </button>
        </div>
      </header>

      {modalOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}
        >
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-lg w-full p-6 shadow-2xl">
            <div className="flex items-start justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-100">About This Tool</h2>
              <button
                onClick={() => setModalOpen(false)}
                className="text-slate-500 hover:text-slate-300 text-xl leading-none ml-4 transition-colors"
              >
                ×
              </button>
            </div>
            <div className="space-y-3 text-sm text-slate-400 leading-relaxed">
              <p>
                Predictions from a gradient-boosted model trained on San Diego crash records
                2016–2024. The label window is 2025–2027; 2025 outcomes are now complete and
                validate the model. 2026–2027 outcomes will be available by 2029.
              </p>
              <p>
                The model's primary signals are crash-timing features: how recently an intersection
                had its last crash, and whether crash frequency structurally accelerated from a
                previously stable baseline (changepoint detection). Cumulative crash volume
                outweighs short-term recency. Built-environment features (road geometry, signals)
                show a small but consistent positive signal on top of crash history alone, though
                the sample is still too small to require them, so the model reported here stays
                crash-history only.
              </p>
              <p>
                San Diego's current annual safety review identifies intersections with five or more
                prior crashes, by definition, none of the 108 confirmed 2025 emergent sites shown on
                this map would appear on that list. This tool identifies the sites the current
                approach cannot see.
              </p>
              <p className="text-xs text-slate-600 italic">Publication forthcoming.</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
