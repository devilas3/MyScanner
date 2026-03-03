# Daily refresh and cron job setup

This guide walks you through wiring the frontend to your API and setting up a daily cron job so your scanner always has fresh data.

---

## 1. Frontend wired to your API

The frontend is already pointed at your Render API:

- **API URL:** `https://myscanner-81ql.onrender.com`
- **File:** `frontend/app.js` → `API_BASE_URL = "https://myscanner-81ql.onrender.com"`

**Test the frontend:**

1. Open `frontend/index.html` in a browser (or run `cd frontend && python -m http.server 8080` and go to `http://localhost:8080`).
2. Pick a date, click **Load pivots** or **Run scan** (or **R1 Pivot Breakout**).
3. If you see data or “0 rows”, the API is working. If you see CORS or network errors, the backend allows all origins by default, so check the API URL and that the service is running.

**If you host the frontend on Hostinger:**

- Upload the contents of the `frontend/` folder to `public_html` (or e.g. `public_html/scanner/`).
- Keep `API_BASE_URL` as above (or change it in `app.js` if you later move the API).
- Open `https://yourdomain.com/` or `https://yourdomain.com/scanner/` and use the scanner as above.

---

## 2. What the daily refresh does

When you call **POST /api/refresh** (with the secret header), the backend:

1. Fetches the latest OHLC data for the configured equity symbols (e.g. via yfinance).
2. Inserts/updates rows in the `ohlc` table.
3. Computes pivot levels (P, R1, R2, S1, S2) for new dates and saves them in the `pivots` table.

After that, “Load pivots” and “Run scan” in the frontend use this up‑to‑date data.  
You want this to run **once per day**, e.g. after NSE market close (3:30 PM IST), so a cron job is used to call `/api/refresh` daily.

---

## 3. Get your refresh secret from Render

The refresh endpoint only runs if the request includes the correct secret.

1. Go to [dashboard.render.com](https://dashboard.render.com) and open your **Web Service** (e.g. myscanner-81ql).
2. In the left sidebar, click **Environment**.
3. Find **REFRESH_SECRET**. If you don’t see it, add a new variable:
   - **Key:** `REFRESH_SECRET`
   - **Value:** a long random string (e.g. `nse-scanner-refresh-7f9a2e4b8c1d3e5f` or generate one).
4. Copy the value and keep it somewhere safe (you’ll use it in the cron job).  
   Do **not** put this value in the frontend or in public repos.

---

## 4. Set up the cron job (cron-job.org)

Use a free external cron service to call your refresh URL every day.

### Step 1: Create an account

1. Go to [cron-job.org](https://cron-job.org).
2. Sign up (free account is enough).

### Step 2: Create a new cron job

1. After logging in, click **Cronjobs** → **Create cronjob** (or **Create**).
2. Fill in:

   | Field | Value |
   |--------|--------|
   | **Title** | `NSE Scanner daily refresh` (or any name) |
   | **Address (URL)** | `https://myscanner-81ql.onrender.com/api/refresh` |
   | **Request method** | **POST** (not GET) |
   | **Request timeout** | e.g. **60** seconds |

### Step 3: Add the secret header

The backend expects the secret in a header.

1. In the same cron job form, find **Request headers** or **Advanced** → **Headers**.
2. Add one header:
   - **Name:** `X-Refresh-Secret`
   - **Value:** the exact `REFRESH_SECRET` value from Render (from step 3 above).

Save the header.

### Step 4: Set the schedule

1. Set **Schedule** to run once per day.
2. Choose a time **after NSE market close** so that the day’s data is available, e.g.:
   - **6:00 PM IST** (12:30 PM UTC), or  
   - **7:00 PM IST** (1:30 PM UTC).

   In cron-job.org you can often pick “Daily” and then set the hour/minute (use UTC if it asks for server time).

3. Save the cron job.

### Step 5: Test the refresh once

1. In cron-job.org, open your cron job and use **Run now** / **Execute** (if available).
2. Check your Render **Logs** for the service. You should see the refresh run (and no 401 Unauthorized).
3. In the frontend, load pivots or run a scan for **today’s date** (after the run). You should see data if the fetch and DB update succeeded.

If you get **401 Unauthorized**, the header name or value is wrong: it must be exactly `X-Refresh-Secret` and the same value as `REFRESH_SECRET` on Render.

---

## 5. Summary checklist

| Step | What to do |
|------|------------|
| 1 | Frontend uses `API_BASE_URL = "https://myscanner-81ql.onrender.com"` in `app.js`. |
| 2 | On Render, note or set **REFRESH_SECRET** under Environment. |
| 3 | On cron-job.org, create a **POST** job to `https://myscanner-81ql.onrender.com/api/refresh`. |
| 4 | Add header **X-Refresh-Secret** = your REFRESH_SECRET value. |
| 5 | Schedule the job **daily** after market close (e.g. 6:00 PM IST). |
| 6 | Run the job once manually and check Render logs and the frontend. |

---

## 6. Optional: one-time backfill (historical data)

If you want past dates (e.g. last 1 year) to have data:

1. On your machine, open a terminal in the project.
2. Set the same database URL that Render uses (Supabase **pooler** URI).
3. Run the backfill script once:

   ```bash
   cd backend
   source .venv/bin/activate   # or: .venv\Scripts\activate on Windows
   export DATABASE_URL="postgresql://postgres.PROJECT_REF:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres"
   python scripts/backfill.py
   ```

4. After it finishes, the daily cron will only add new days; the backfill does not need to run again unless you reset the DB.

---

## 7. Troubleshooting

- **CORS errors in browser:** The backend is set to allow all origins (`*`). If you still see CORS errors, confirm the request URL is exactly `https://myscanner-81ql.onrender.com` (no typo, HTTPS).
- **401 on /api/refresh:** Header must be `X-Refresh-Secret` and the value must match Render’s `REFRESH_SECRET`.
- **No data for today:** Run the refresh once (cron “Run now” or a manual POST with the secret header). Allow a few minutes for the job to finish, then try “Load pivots” again for today’s date.
- **Render free tier spins down:** The first request after idle can be slow; the cron job may need a longer timeout (e.g. 60–120 seconds).
