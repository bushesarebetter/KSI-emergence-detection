/** @type {import('tailwindcss').Config} */

/**
 * Design tokens for a civic broadsheet, not a SaaS dashboard.
 *
 * The subject is people being killed and seriously injured at street corners.
 * The reference class is public-health reporting and transit signage — the
 * Swiss/civic tradition — rather than analytics UI. Three decisions follow:
 *
 * 1. PAPER GROUND. The Google basemap renders light. A dark chrome wrapped
 *    around a light map reads as broken, and forces a Cloud-console dark style
 *    just to look finished. A warm paper ground works *with* the map and reads
 *    as a printed document.
 * 2. COLOUR IS RESERVED FOR RISK. Everything structural is ink on paper. The
 *    only saturated colour in the interface is the risk ramp, so a red dot means
 *    something instead of competing with a red button.
 * 3. HAIRLINES, NOT CARDS. Rules and whitespace separate content. Rounded boxes
 *    with borders and shadows are the visual signature this design is avoiding.
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Newsreader: editorial serif with real optical character. Carries the
        // voice — headlines, pull-figures, anything making a claim.
        serif: ['"Newsreader"', "Georgia", "serif"],
        // Public Sans is the typeface of the U.S. Web Design System, drawn for
        // government services. A contextual choice, not a decorative one.
        sans: ['"Public Sans"', "Helvetica Neue", "Arial", "sans-serif"],
        // Tabular data and coordinates.
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        paper: {
          DEFAULT: "#FBF9F5", // main ground, warm off-white
          sunk: "#F2EEE6", // recessed panels
          edge: "#EAE4D9", // tinted blocks
        },
        rule: {
          DEFAULT: "#DCD5C7", // hairlines
          strong: "#B8AF9C", // emphasised rules
        },
        ink: {
          DEFAULT: "#17150F", // primary text, warm near-black
          2: "#55503F", // secondary
          3: "#8A8272", // tertiary / captions
        },
        // Sequential risk ramp, dark→light. Colourblind-safe ordering is carried
        // by lightness, so the tiers remain distinguishable in greyscale.
        risk: {
          1: "#7F1D1D", // rank 1–50      oxblood
          2: "#C2410C", // rank 51–100    burnt orange
          3: "#D97706", // rank 101–200   amber
          4: "#E8B563", // rank 201–500   pale amber
        },
      },
      letterSpacing: {
        label: "0.14em", // small-caps interface labels
      },
      boxShadow: {
        // A printed card lifted off paper, not a glowing surface.
        paper: "0 1px 2px rgba(23,21,15,0.06), 0 8px 24px -12px rgba(23,21,15,0.18)",
      },
      maxWidth: {
        measure: "34ch", // editorial line length for the standfirst
      },
    },
  },
  plugins: [],
};
