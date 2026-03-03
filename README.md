# NSE Equity Stock Scanner

Backend: FastAPI (Python) with yfinance + PostgreSQL/SQLite.  
Frontend: Static HTML/CSS/JS (Hostinger) calling the API.

## Project layout

- `backend/` – FastAPI app (deploy to Render/Railway/PythonAnywhere)
  - `.env.example` – template for environment variables (copy to `.env` and fill in; see [Environment variables](#environment-variables))
  - `app/main.py` – API entrypoint and routes (`/api/pivots`, `/api/r1-breakouts`, `/api/scan`, `/api/refresh`)
  - `app/db.py` – SQLAlchemy models and session (`ohlc`, `pivots`, `refresh_log`)
  - `app/config.py` – loads `.env`; reads `DATABASE_URL`, `REFRESH_SECRET`, CORS origins
  - `app/bhavcopy_fetcher.py` – yfinance-based OHLC fetch + daily refresh helpers
  - `app/pivot.py` – classic floor pivots and R1 breakout logic
  - `app/condition_engine.py` – safe expression evaluator for user conditions
  - `scripts/backfill.py` – one-time equity backfill + pivot computation
- `frontend/`
  - `index.html` – UI (segment selector, date, conditions, R1 Pivot Breakout button)
  - `style.css` – modern, responsive layout
  - `app.js` – calls backend API and renders tables

## Environment variables

The backend reads configuration from environment variables. For local development, use a `.env` file in the `backend/` directory.

1. Copy the example file and edit it with your values:

   ```bash
   cd backend
   cp .env.example .env
   ```

2. Edit `backend/.env` and set at least:
   - **`DATABASE_URL`** – PostgreSQL connection string (e.g. from Supabase: Project Settings → Database → Connection string URI). If your password contains special characters like `[`, `]`, `{`, `}`, URL-encode them (e.g. `[` → `%5B`, `]` → `%5D`).
   - **`REFRESH_SECRET`** – A long random string used to protect the `POST /api/refresh` endpoint (for cron jobs).

Do **not** commit `.env`; it is listed in `.gitignore`. On Render or other hosts, set these variables in the service’s environment configuration instead of using a file.

## Running locally

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Option A: use .env (recommended – copy from .env.example and fill in)
# Option B: set in shell
# export DATABASE_URL="sqlite:///./scanner.db"  # or your Postgres URL
# export REFRESH_SECRET="your-refresh-secret"

uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend

Open `frontend/index.html` directly in the browser, or serve it with a simple static server:

```bash
cd frontend
python -m http.server 8080
```

Make sure `API_BASE_URL` in `frontend/app.js` matches your backend URL (default: `http://localhost:8000` for local dev).

## Deployment – Option A (Backend on Render, Frontend on Hostinger)

### 1. Database (Supabase or Neon)

1. Create a free PostgreSQL project on Supabase or Neon.
2. Copy the database connection string (e.g. `postgresql://user:pass@host:5432/dbname`).
3. Use it as `DATABASE_URL` in your backend environment.
4. On first run, the app will create the `ohlc`, `pivots`, and `refresh_log` tables automatically.

### 2. Backend (Render)

1. Push this project to GitHub.
2. On `render.com`, create a new **Web Service**:
   - Repo: your GitHub repo
   - **Root Directory:** `backend` (required – `requirements.txt` is inside `backend/`)
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`  
     (enter only this – do not add `start` or any other word in front)
   - If you use the repo’s `render.yaml`, Root Directory is set automatically.
3. Set environment variables:
   - `DATABASE_URL` – PostgreSQL URL from Supabase/Neon
   - `REFRESH_SECRET` – long random string
   - (optional) `CORS_ORIGINS` – you can hardcode origins in code instead if easier
4. Deploy and note the service URL (e.g. `https://your-scanner.onrender.com`).

### 3. Daily refresh job (cron)

1. In `cron-job.org` (or similar free cron service), create a daily job (e.g. 6:00 PM IST).
2. Method: `POST` to:
   - `https://your-scanner.onrender.com/api/refresh`
3. Add a header:
   - `X-Refresh-Secret: <your REFRESH_SECRET>`

This will:

- Fetch the latest OHLC data (yfinance, configurable symbol list in `bhavcopy_fetcher.py`)
- Insert/update records in `ohlc`
- Compute pivots for new dates and save them in `pivots`

### 4. Frontend (Hostinger shared hosting)

1. In `frontend/app.js`, set:

   ```js
   const API_BASE_URL = "https://your-scanner.onrender.com";
   ```

2. In Hostinger hPanel, open File Manager (or use FTP).
3. Upload the contents of the `frontend/` folder (`index.html`, `style.css`, `app.js`) into `public_html` (or a subfolder like `public_html/scanner`).
4. Visit your site, e.g.:
   - `https://yourdomain.com/` or `https://yourdomain.com/scanner/`

The page will:

- Load the condition editor and tables
- Call:
  - `GET /api/pivots?date=YYYY-MM-DD&segment=equity`
  - `POST /api/scan` with body: `{ date, segment, conditions: [...], combine }`
- Render the “Daily Pivots” and “Scan Results” tables
- Run “R1 Pivot Breakout” using the preset condition: `high >= r1 and close > r1`

### 5. One-time backfill

1. Run locally:

   ```bash
   cd backend
   source .venv/bin/activate
   export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
   python -m app.db  # or run any script that triggers init_db()
   python scripts/backfill.py
   ```

2. This will fetch ~1 year of equity data (yfinance) for the configured symbols and compute pivots.

After this, the daily cron keeps the database up to date.

