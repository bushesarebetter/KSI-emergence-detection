import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),

    /**
     * Installable web app.
     *
     * Saves to a phone's home screen from the browser with no app store, no
     * developer accounts, and no Mac -- the things the native Expo scaffold in
     * mobile/ cannot avoid. Once installed, the shell and the model export are
     * cached so the map opens instantly and works without signal.
     *
     * Google Maps tiles and scripts are deliberately NOT cached: their terms
     * forbid it and they are served with their own caching anyway. Anything not
     * matched below goes straight to the network.
     */
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/*.png", "og-card.png"],
      manifest: {
        name: "San Diego Intersection Risk",
        short_name: "Intersection Risk",
        description:
          "A ranking of San Diego intersections with no serious-crash history, ordered by how likely they are to have one.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        theme_color: "#FBF9F5",
        background_color: "#FBF9F5",
        categories: ["navigation", "government", "utilities"],
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // Precache the shell. The 1.6 MB geojson is intentionally excluded here
        // and handled at runtime below, so a new model export is picked up on
        // next visit rather than pinned until the service worker changes.
        globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        runtimeCaching: [
          {
            // Model output: serve cached immediately, refresh in the background.
            urlPattern: ({ url }) => url.pathname.startsWith("/data/"),
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "ksi-data",
              expiration: { maxEntries: 4, maxAgeSeconds: 7 * 24 * 60 * 60 },
            },
          },
          {
            urlPattern: ({ url }) =>
              url.origin === "https://fonts.googleapis.com" ||
              url.origin === "https://fonts.gstatic.com",
            handler: "CacheFirst",
            options: {
              cacheName: "fonts",
              expiration: { maxEntries: 20, maxAgeSeconds: 365 * 24 * 60 * 60 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],

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
