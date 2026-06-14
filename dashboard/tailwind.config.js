/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      spacing: {
        70: "17.5rem",
        90: "22.5rem",
      },
      width: {
        70: "17.5rem",
        90: "22.5rem",
      },
      colors: {
        accent: {
          DEFAULT: "#f97316",
          dim: "#7c2d12",
        },
      },
    },
  },
  plugins: [],
};
