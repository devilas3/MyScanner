# Backfill (2 years) and validate everything is connected

---

## Part 1: Backfill data for the last 2 years

Backfill runs **on your machine** and writes into the **same Supabase DB** your Render app uses. Use the **pooler** connection string (same as in Render).

### 1. Get your database URL

- From **Render** → your service → **Environment** → copy `DATABASE_URL`, or  
- From **Supabase** → Project Settings → Database → **Connection string** → **Transaction** (port 6543).

It should look like:
`postgresql://postgres.xxxxx:PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres`

### 2. Run the backfill (2 years)

In a terminal, from your project root:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Use the same DATABASE_URL as Render (pooler URI)
export DATABASE_URL="postgresql://postgres.xxxxx:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres"

# Backfill last 2 years (default)
python scripts/backfill.py

# Or specify years
python scripts/backfill.py --years 2

# Or exact date range
python scripts/backfill.py --start 2023-03-01 --end 2025-03-02
```

- **Default:** `--years 2` (about 730 days up to today).  
- **Custom range:** `--start YYYY-MM-DD --end YYYY-MM-DD`.  
- The script will print progress (fetching OHLC, upserting, computing pivots). When it says "Backfill done.", the DB has data for that range.

### 3. If you see errors

- **No data returned:** Check internet; yfinance can throttle. Try a shorter range (e.g. `--years 0.5`).  
- **Database connection error:** Confirm `DATABASE_URL` is the **pooler** URI (port 6543) and password is URL-encoded if it has special characters.

---

## Part 2: Validate everything is connected

Use this checklist to confirm: **API → Database**, **Frontend → API**, and **Cron → API**.

### Check 1: API is up and responding

1. Open in a browser:
   - **API root:** https://myscanner-81ql.onrender.com  
   - You should see a small JSON (e.g. docs or welcome), or at least no connection error.
2. **Docs (optional):** https://myscanner-81ql.onrender.com/docs  
   - Swagger UI should load.

If the first request is slow, that’s normal on Render free tier (cold start).

---

### Check 2: Database has data (API ↔ DB)

1. Pick a **date that’s in your backfill range** (e.g. a recent weekday).
2. Open (replace the date if you like):
   - https://myscanner-81ql.onrender.com/api/pivots?date=2025-02-28&segment=equity
3. You should see **JSON** with an array of pivot rows (symbol, pivot, r1, r2, s1, s2).  
   - If the array is **empty** `[]`, either that date has no data or backfill didn’t run for that date.  
   - If you see **multiple objects** with symbol names and numbers, **API and DB are connected** and have data.

---

### Check 3: Frontend is connected to the API

1. Open your **Hostinger** site: https://taazikhabar.in (or https://taazikhabar.in/scanner/ if you use a subfolder).
2. In the scanner page:
   - Choose a **date** that you know has data (from Check 2).
   - Click **“Load pivots”**.
3. The **Daily Pivots** table should fill with rows (symbol, P, R1, R2, S1, S2).  
4. Click **“R1 Pivot Breakout”** or **“Run scan”** with a condition (e.g. `close > r1`).  
   - The **Scan Results** table should show rows or “0 rows” (no errors).

If you see **CORS or network errors** in the browser console (F12 → Console), the frontend is not reaching the API: confirm `API_BASE_URL` in `frontend/app.js` is exactly `https://myscanner-81ql.onrender.com` (no trailing slash) and that the API is up (Check 1).

---

### Check 4: Cron job is connected to the API

1. In **cron-job.org**, open your refresh job and check **“Last run”** or **“Log” / “Response”**.
2. You should see:
   - **HTTP 200** and response body `{"status":"ok"}` (or `{"status":"error","message":"..."}` if something failed), and  
   - No “output too large” or connection timeout.
3. Optionally trigger **“Run now”** and then:
   - In **Render** → **Logs**, confirm a request to `/api/refresh` and no 401.  
   - After a few minutes, call the pivots URL for **today’s date** (or latest trading day). If you see new data, the cron ran and the DB was updated.

---

## Quick reference

| What you’re checking      | How to validate |
|---------------------------|------------------|
| API is up                 | Open https://myscanner-81ql.onrender.com (and /docs) |
| DB has data               | GET /api/pivots?date=YYYY-MM-DD&segment=equity returns non-empty JSON |
| Frontend → API            | On https://taazikhabar.in, “Load pivots” and “Run scan” work |
| Cron → API                | cron-job.org shows 200 and `{"status":"ok"}`, Render logs show /api/refresh |

---

## Summary

- **Backfill (2 years):** Run `python scripts/backfill.py` (or `--years 2`) in `backend/` with `DATABASE_URL` set to your Supabase **pooler** URI.  
- **Validate:** Use the four checks above to confirm API, DB, frontend, and cron are all connected and working.
