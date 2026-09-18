# Hosting the dashboard on Render

The dashboard is a static Vite/React build. Nothing runs server-side: the model is
fit offline and its output ships as two files in `dashboard/public/data/`. That
means it deploys as a Render **Static Site**, not a Web Service — which matters,
because Render static sites are free, globally CDN-cached, and never spin down.
A Web Service on the free tier sleeps after 15 minutes of inactivity and takes
~50 seconds to wake, which would be a poor first impression for anyone you emailed
a link to.

Total cost at the settings below: **$0/month on Render**, plus Google Maps usage
(see §5 — also $0 at this traffic level, but the free tier is per-API, not a
shared credit).

---

## 1. Get the Google Maps credentials first

The site will build without these but the map will render an error panel, so do
this before deploying.

### 1.1 Create the Cloud project and key

1. Go to <https://console.cloud.google.com/> and create a project, e.g. `ksi-emergence`.
2. **Billing must be enabled** on the project. Maps returns watermarked, degraded
   tiles without it even inside the free allowance. You will not be charged at this
   traffic level, but Google requires a card on file.
3. **APIs & Services → Library** → enable exactly these:
   - **Maps JavaScript API** — the basemap and the deck.gl overlay
   - **Street View Static API** — the embedded pano in the detail panel
4. **APIs & Services → Credentials → Create credentials → API key**. Copy it.

### 1.2 Restrict the key (do not skip this)

An unrestricted Maps key in a public repo's deployed bundle will be scraped and
run up against your quota. On the key's settings page:

- **Application restrictions → Websites**. Add:
  ```
  https://ksi-emergence-detection.onrender.com/*
  https://your-custom-domain.org/*
  http://localhost:5173/*
  ```
- **API restrictions → Restrict key** → select only Maps JavaScript API and
  Street View Static API.

The key is necessarily visible in the client bundle — that is normal and expected
for browser Maps keys. The referrer restriction is what protects it, not secrecy.

### 1.3 Create a Map ID

Vector rendering (which deck.gl's overlay needs) requires a Map ID, and the dark
styling lives on the Map ID rather than in code — `google.maps.Map`'s `styles`
option is silently ignored whenever a `mapId` is set.

1. **Google Maps Platform → Map Management → Create Map ID**.
2. Name it `ksi-dashboard`, **Map type: JavaScript**, **Rendering: Vector**.
3. Tick **Tilt** and **Rotation** if you want 3D camera control.
4. Create a **Map style** (Map Styles → Create style → start from "Dark"), then
   associate it with the Map ID you just made.
5. Copy the Map ID (looks like `8e0a97af9386fef`).

---

## 2. Create the Render static site

1. Push the repo to GitHub.
2. <https://dashboard.render.com> → **New → Static Site** → connect the repo.
3. Fill in exactly:

| Setting | Value |
|---|---|
| **Name** | `ksi-emergence-detection` (becomes `ksi-emergence-detection.onrender.com`) |
| **Branch** | `master` |
| **Root Directory** | `dashboard` |
| **Build Command** | `npm ci && npm run build` |
| **Publish Directory** | `dist` |

`npm ci` rather than `npm install`: it installs exactly what `package-lock.json`
pins, so a Render build can never silently pick up a different dependency version
than the one you tested locally.

`Root Directory` is the setting people miss. Without it Render runs the build at
the repo root, finds no `package.json`, and fails.

### 2.1 Environment variables

**Environment → Add Environment Variable**:

| Key | Value |
|---|---|
| `VITE_GOOGLE_MAPS_API_KEY` | the key from step 1.1 |
| `VITE_GOOGLE_MAPS_MAP_ID` | the Map ID from step 1.3 |
| `NODE_VERSION` | `20` |

Vite inlines `VITE_`-prefixed variables at **build** time, not runtime. So after
changing either value you must **Manual Deploy → Clear build cache & deploy** —
a plain redeploy can reuse the cached bundle and your change will appear to do
nothing.

`NODE_VERSION` is worth setting explicitly; Render's default has moved before, and
Vite 5 wants Node 18+.

### 2.2 Redirects and rewrites

**Redirects/Rewrites → Add Rule**:

| Source | Destination | Action |
|---|---|---|
| `/*` | `/index.html` | **Rewrite** |

This is Render's equivalent of the existing `dashboard/vercel.json`. It makes
direct navigation to any deep link serve the app rather than a 404. **Action must
be Rewrite, not Redirect** — a redirect would change the URL in the address bar
and break deep links.

### 2.3 Headers

**Headers → Add Header**. These are optional but `intersections.geojson` is 1.6 MB,
so caching it properly is the difference between a snappy repeat visit and a
1.6 MB download every time.

| Path | Name | Value |
|---|---|---|
| `/assets/*` | `Cache-Control` | `public, max-age=31536000, immutable` |
| `/data/*` | `Cache-Control` | `public, max-age=3600, must-revalidate` |
| `/*` | `X-Content-Type-Options` | `nosniff` |
| `/*` | `Referrer-Policy` | `strict-origin-when-cross-origin` |

`/assets/*` is content-hashed by Vite, so it is safe to cache forever. `/data/*` is
not hashed and changes whenever you re-export the model, hence the one-hour TTL.

Do **not** add a restrictive `Content-Security-Policy` without testing — Google
Maps loads scripts, styles, workers, and image tiles from several `*.googleapis.com`
and `*.gstatic.com` origins, and a strict policy will silently blank the map.

---

## 3. Custom domain

1. Render dashboard → your site → **Settings → Custom Domains → Add**.
2. Enter the domain, then add the DNS record Render shows you:
   - subdomain (`www.ksi-emergence.com`) → **CNAME** → `ksi-emergence-detection.onrender.com`
   - apex (`example.org`) → **A** record → the IP Render gives you
3. Render issues a Let's Encrypt certificate automatically once DNS resolves,
   usually within minutes.
4. **Go back and add the new domain to the Google Maps key referrer list** (step
   1.2). Forgetting this is the single most common cause of "the map worked on
   `.onrender.com` and broke on the real domain".

---

## 4. Updating the data

There is no database and no build-time data generation — the two files in
`dashboard/public/data/` are committed to the repo. To publish a new model run:

```bash
python scripts/build_export_panel_verified.py --run forward
git add dashboard/public/data/
git commit -m "Update dashboard export"
git push
```

Render auto-deploys on push to the configured branch. Build takes roughly a minute.

If you would rather not commit a 1.6 MB file on every model run, the alternative is
to upload the two files to object storage (Cloudflare R2 has a generous free tier)
and point `useIntersections.js` at that URL — the mobile app already works this way
via `DATA_BASE_URL`. Worth doing if exports become frequent; overkill otherwise.

---

## 5. What this will cost

**Render:** $0. Static sites on the free tier include 100 GB/month bandwidth and
custom domains with TLS. The whole site is ~2.5 MB including the data, so 100 GB is
roughly 40,000 full first-time visits.

**Google Maps:** free within normal traffic for this project, but read the
structure before relying on that.

Google **removed the old $200 monthly credit on 1 March 2025** and replaced it with
a per-SKU free allowance. Each API now has its own monthly quota rather than
drawing on one shared pot:

| SKU | Tier | Free / month | Price after |
|---|---|---:|---|
| Maps JavaScript API (the basemap) | Essentials | 10,000 loads | $7 per 1,000 |
| Street View Static API (the pano panel) | Essentials | 10,000 loads | $7 per 1,000 |

These are separate buckets: exhausting map loads does not consume the Street View
allowance. One dashboard visit is one map load; one intersection click that renders
the pano panel is one Street View event.

Ten outreach emails will generate on the order of 50-200 visits, so this project
sits far inside the free tier. But note what changed: **there is no longer any
credit cushion.** Under the old model, overage ate into $200 before costing
anything; now the 10,001st load bills immediately. A scraped key doing 100k loads
would be roughly $630.

So these two are load-bearing, not optional:

1. **Referrer restrictions** (step 1.2) are the actual defence. A key locked to
   your domains cannot be used from anyone else's site. This is the one that
   matters.
2. **A hard daily quota cap.** APIs & Services → Maps JavaScript API → Quotas →
   set something like 500/day. If anything goes wrong the map degrades for the rest
   of the day instead of billing you. Do the same for Street View Static.
3. **Google Cloud → Billing → Budgets & alerts** → a $1 budget alerting at 100%,
   so you hear about any spend at all the moment it happens.

One design consequence worth knowing: `StreetViewPanel` fetches a pano on every
intersection selection. A reviewer clicking through 30 sites burns 30 Street View
events. Still trivial at these volumes, but it is why the two SKUs are capped
separately above.

Pricing changes; verify against
<https://developers.google.com/maps/billing-and-pricing/pricing> before quoting
these figures to anyone.

---

## 6. Pre-launch checklist

Before sending the link to anyone on the outreach list:

- [ ] Map renders with the dark style (not the grey "for development purposes only" watermark — that means billing is off)
- [ ] Street View panel loads for a top-10 intersection, and degrades to "No Street View coverage here" rather than erroring on an obscure one
- [ ] Deep link to a sub-path loads the app instead of a 404 (confirms the rewrite rule)
- [ ] Browser console is clean — in particular no `RefererNotAllowedMapError`, which means the deployed domain is missing from the key restrictions
- [ ] Works on a phone; the layout is tight at narrow widths
- [ ] The methodology link in the header resolves to something a traffic engineer can read
- [ ] Google Cloud budget alert is configured
- [ ] Dates and figures on the page match `reports/verified_canonical_numbers.json`

That last one matters more than it sounds. The outreach emails cite specific
numbers, and the fastest way to lose a technical reader is a dashboard that
disagrees with the email that brought them to it.
