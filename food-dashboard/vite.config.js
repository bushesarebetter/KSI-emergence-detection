import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),

    /**
     * Installable web app, same arrangement as the intersection site: the
     * shell is precached, the export is served stale-while-revalidate so a new
     * one is picked up on the next visit, and Google's tiles are never cached.
     */
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icons/*.png", "og-card.png"],
      manifest: {
        name: "San Diego Food Safety Risk",
        short_name: "Food Safety Risk",
        description:
          "San Diego restaurants, markets and food trucks ranked by how likely the County's next inspection is to find a major violation, with what inspectors found last time.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "portrait",
        theme_color: "#FBF9F5",
        background_color: "#FBF9F5",
        categories: ["food", "health", "utilities"],
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "/icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,svg,woff2}"],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/data/"),
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "food-data",
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
        manualChunks: {
          deck: ["@deck.gl/core", "@deck.gl/layers", "@deck.gl/google-maps"],
          charts: ["recharts"],
          react: ["react", "react-dom"],
        },
      },
    },
  },
});
