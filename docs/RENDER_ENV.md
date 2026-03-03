# Set environment variables on Render

In **Dashboard → Your Web Service → Environment**, add:

| Key | Where to get the value |
|-----|------------------------|
| **DATABASE_URL** | **Use Supabase pooler (Transaction) URI** – see below. Do **not** use the direct DB URI on Render (IPv6 unreachable). |
| **REFRESH_SECRET** | A long random string. Use the same value in cron-job.org as the header `X-Refresh-Secret` when calling `POST /api/refresh`. |

## DATABASE_URL and Render (Supabase)

Render’s network is **IPv4-only**. Supabase’s direct database host (`db.xxx.supabase.co`) can resolve to IPv6, which causes **“Network is unreachable”**.

**Fix:** Use the **connection pooler** (Transaction mode) URI from Supabase instead of the direct database URI.

1. In [Supabase Dashboard](https://supabase.com/dashboard) open your project.
2. Go to **Project Settings** (gear) → **Database**.
3. Under **Connection string**, choose **URI**.
4. Select the **Transaction** (or **Session**) pooler – not “Direct connection”.
5. Copy the URI. It will look like:
   - `postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres`
   - Port **6543** = transaction pooler (IPv4-friendly).
6. If your password has special characters, URL-encode them (e.g. `[` → `%5B`, `]` → `%5D`).
7. In Render → your service → **Environment**, set **DATABASE_URL** to this pooler URI.

**Steps on Render:**

1. Open your service on [dashboard.render.com](https://dashboard.render.com).
2. Click **Environment** in the left sidebar.
3. Add or edit **DATABASE_URL** with the **pooler** URI from Supabase.
4. Add **REFRESH_SECRET** with a long random string.
5. Save. Render will redeploy.
