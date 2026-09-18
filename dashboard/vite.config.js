import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // deck.gl and recharts are both large and change far less often than app
        // code. Splitting them keeps the app chunk small enough that a data or UI
        // tweak doesn't invalidate ~1 MB of cached vendor JS for every visitor.
        manualChunks: {
          deck: ["@deck.gl/core", "@deck.gl/layers", "@deck.gl/google-maps"],
          charts: ["recharts"],
          react: ["react", "react-dom"],
        },
      },
    },
  },
});
