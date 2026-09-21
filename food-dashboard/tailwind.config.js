/** @type {import('tailwindcss').Config} */

/**
 * The same tokens as the intersection site: a civic broadsheet on warm paper,
 * ink for everything structural, one sequential ramp reserved for risk. Kept
 * identical on purpose, so the two sites read as one publication.
 */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Newsreader"', "Georgia", "serif"],
        sans: ['"Public Sans"', "Helvetica Neue", "Arial", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        paper: {
          DEFAULT: "#FBF9F5",
          sunk: "#F2EEE6",
          edge: "#EAE4D9",
        },
        rule: {
          DEFAULT: "#DCD5C7",
          strong: "#B8AF9C",
        },
        ink: {
          DEFAULT: "#17150F",
          2: "#55503F",
          3: "#8A8272",
        },
        risk: {
          1: "#7F1D1D",
          2: "#C2410C",
          3: "#D97706",
          4: "#E8B563",
        },
      },
      letterSpacing: {
        label: "0.14em",
      },
      boxShadow: {
        paper: "0 1px 2px rgba(23,21,15,0.06), 0 8px 24px -12px rgba(23,21,15,0.18)",
      },
      maxWidth: {
        measure: "34ch",
      },
    },
  },
  plugins: [],
};
