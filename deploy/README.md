# Portal demo site (Cloudflare Pages)

`deploy/site/` is a static snapshot of the client portal, filled with **fictional** demo data. It shows a client view and a staff view. Every form leads to a "demo: not saved" page, every page is marked `noindex`, and there's no back end and no real data.

Rebuild it after any portal change:

```bash
python deploy/build_static_demo.py      # rewrites deploy/site/
python -m pytest tests/test_static_demo.py
```

⚠ Never point the exporter at real client folders. Its output is public.

## Put it on Cloudflare Pages (pick one)

**A. Drag and drop (2 minutes, no tools).** Cloudflare dashboard → Workers & Pages → Create → Pages → **Upload assets** → project name `tbcco-portal-demo` → drop in `portal-demo-site.zip` (or the `deploy/site` folder) → Deploy. You get `https://tbcco-portal-demo.pages.dev`. To update it, open the project → Create deployment → upload again.

**B. Connect this GitHub repo (auto-deploys on every push).** Workers & Pages → Create → Pages → **Connect to Git** → pick this repository → production branch `main` (or this dev branch) → Framework preset: *None* → Build command: *(leave empty)* → Build output directory: `deploy/site` → Save and Deploy. Every push that changes `deploy/site/` redeploys, and other branches get their own preview URLs.

**C. Command line (from your own computer).**
```bash
npx wrangler pages project create tbcco-portal-demo --production-branch main
npx wrangler pages deploy deploy/site --project-name tbcco-portal-demo
```

## Letting Claude deploy it

Create a Cloudflare API token (My Profile → API Tokens → Custom token, permission **Account → Cloudflare Pages → Edit**). Add it to this cloud environment's settings under **Network secrets** for host `api.cloudflare.com`. A new session picks it up, and Claude can then run option C itself.
