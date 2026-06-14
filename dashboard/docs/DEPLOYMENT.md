# Deployment

## Vercel (Recommended)

1. Push the repository to GitHub.
2. Go to [vercel.com](https://vercel.com) and import the repository.
3. Set the **Root Directory** to `dashboard`.
4. Under **Environment Variables**, add:
   - Name: `VITE_MAPBOX_TOKEN`
   - Value: your Mapbox public token (starts with `pk.`)
5. Click **Deploy**.

Vercel will run `npm run build` and serve the output. The `vercel.json` rewrite rule ensures client-side routing works on direct URL access.

The files in `dashboard/public/data/` are committed to the repository and served as static assets — they do not need to be generated at build time.

To update the data, run the export script locally, commit the updated files, and push. Vercel redeploys automatically on push.

---

## Custom Domain

In the Vercel project settings, go to **Domains** and add your custom domain. Vercel provisions a TLS certificate automatically via Let's Encrypt. Point your DNS CNAME record to `cname.vercel-dns.com` (or use Vercel's nameservers for apex domains). Propagation typically takes a few minutes.
