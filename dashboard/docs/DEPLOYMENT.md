# Deployment

The dashboard is a static Vite build with no server component — the model runs
offline and its output ships as two files in `public/data/`.

**The full walkthrough is `docs/HOSTING_RENDER.md` in the repo root.** It covers
the Google Cloud setup, exact Render settings, the SPA rewrite rule, cache
headers, custom domains, and cost controls. What follows is the short version for
each host.

---

## Render (recommended)

Free, CDN-cached, and static sites never spin down — unlike a free Web Service,
which sleeps after 15 minutes and takes ~50 seconds to wake.

**New → Static Site**, then:

| Setting | Value |
|---|---|
| Root Directory | `dashboard` |
| Build Command | `npm ci && npm run build` |
| Publish Directory | `dist` |

Environment variables: `VITE_GOOGLE_MAPS_API_KEY`, `VITE_GOOGLE_MAPS_MAP_ID`,
`NODE_VERSION=20`.

Redirects/Rewrites: `/*` → `/index.html`, action **Rewrite**.

See `docs/HOSTING_RENDER.md` for cache headers and the pre-launch checklist.

---

## Vercel

Also works, and `vercel.json` in this directory already supplies the SPA rewrite.

1. Import the repository at <https://vercel.com>.
2. Set **Root Directory** to `dashboard`.
3. Add environment variables `VITE_GOOGLE_MAPS_API_KEY` and
   `VITE_GOOGLE_MAPS_MAP_ID`.
4. Deploy.

---

## Important: rebuild after changing keys

Vite inlines `VITE_`-prefixed variables into the bundle at **build** time. Changing
one in the host's dashboard has no effect until you trigger a fresh build with the
cache cleared. On Render that is **Manual Deploy → Clear build cache & deploy**.

## Important: add every domain to the API key

The Maps key is restricted by HTTP referrer. A new custom domain must be added to
the key's allowed referrer list in Google Cloud, or the map fails with
`RefererNotAllowedMapError` while everything else on the page keeps working — which
makes it easy to misdiagnose.

---

## Updating data

`public/data/` is committed to the repo and served as static assets; nothing is
generated at build time.

```bash
python scripts/build_export_panel_verified.py --run forward
git add dashboard/public/data/
git commit -m "Update dashboard export"
git push
```

Both Render and Vercel redeploy automatically on push.
