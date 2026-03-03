# Set environment variables on Render

In **Dashboard → Your Web Service → Environment**, add:

| Key | Where to get the value |
|-----|------------------------|
| **DATABASE_URL** | Your Supabase connection string (Project Settings → Database → Connection string URI). Same value as in `backend/.env` if you use it locally. |
| **REFRESH_SECRET** | A long random string you create. Use the **same** value in cron-job.org as the header `X-Refresh-Secret` when calling `POST /api/refresh`. |

**Steps:**

1. Open your service on [dashboard.render.com](https://dashboard.render.com).
2. Click **Environment** in the left sidebar.
3. Click **Add Environment Variable**.
4. Add `DATABASE_URL` and `REFRESH_SECRET` with your values.
5. Save. Render will redeploy with the new variables.

Do not commit real secrets to the repo. Get **DATABASE_URL** from Supabase; set **REFRESH_SECRET** to a strong random string and reuse it in your cron job.
