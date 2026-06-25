# Kantar BrandEcho Data Assistant

Current full-stack version of the project with:

- Python backend in FastAPI
- React frontend in Vite
- Excel-based data retrieval and analytics
- Groq-powered answer generation

## Current Project Layout

```text
Trial3/
|- api/
|  |- server.py
|- app/
|  |- main.py
|  |- core/
|  |  |- text_utils.py
|  |- services/
|     |- analytics_service.py
|     |- dashboard_service.py
|     |- main_data_service.py
|     |- routing_service.py
|- data/
|  |- Complete-DB.xlsx
|  |- Factors-DB.xlsx
|- frontend/
|  |- package.json
|  |- vite.config.js
|  |- src/
|     |- App.jsx
|     |- components/
|     |- utils/api.js
|- check_groq_limits.py
|- requirements.txt
|- REACT_SETUP.md
|- README.md
```

## What Is Implemented

### Frontend

- Chat workspace with multi-chat state, routing trace panel, and retrieval panel
- Dashboard view with:
- KPI tiles
- Top category by brand chart
- Brand distribution donut by category
- Interactive world map by market coverage
- Market-level breakdown cards

### Backend

- Loads `Complete-DB.xlsx` and `Factors-DB.xlsx` at startup
- Uses Groq client for generation (`GROQ_API_KEY` required)
- Delegates logic to service modules under `app/services/`
- Includes deterministic analytics responses for many analytics-style prompts

## Environment Variables

Create `.env` in project root:

```env
GROQ_API_KEY=your_groq_api_key
SSL_CERT_FILE=optional_path_to_ca_bundle
```

## Local Setup

### 1) Python dependencies

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 2) Frontend dependencies

```powershell
cd frontend
npm install
cd ..
```

## Run

### Backend (FastAPI)

```powershell
python -m api.server
```

Backend URL: `http://localhost:8000`

### Frontend (Vite)

```powershell
cd frontend
npm run dev
```

Frontend URL: `http://localhost:5173`

### Optional legacy app (Streamlit)

```powershell
streamlit run app/main.py
```

## Current FastAPI Endpoints (as implemented)

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Basic service health status |
| POST | `/api/route-query` | Route a user question and merge follow-up context |
| POST | `/api/filter-projects` | Filter projects from Complete-DB using route hints |
| POST | `/api/filter-factors` | Filter factors from Factors-DB and return related projects |
| POST | `/api/fetch-factors` | Fetch factors for supplied project rows |
| POST | `/api/answer` | Generate LLM answer from project/factor context |
| POST | `/api/analytics-answer` | Deterministic and LLM analytics answer path |
| GET | `/api/catalog` | Return catalog summary |
| GET | `/api/dashboard-summary` | Return KPI/chart/slicer payload for dashboard |
| GET | `/api/market-breakdown` | Return category/subcategory and brand breakdown by market |

## Frontend API Calls In Current UI

`frontend/src/App.jsx` currently calls:

- `POST /api/route-query`
- `POST /api/filter-projects`
- `POST /api/filter-factors`
- `POST /api/answer`
- `POST /api/analytics-answer`
- `GET /api/dashboard-summary`

`frontend/src/utils/api.js` also includes a `GET /api/health` helper.

These routes are now implemented in the backend.

## Utility Script

Run Groq quota check:

```powershell
python check_groq_limits.py
```

## Tech Stack

- Frontend: React 18, Vite, react-simple-maps
- Backend: FastAPI, Uvicorn
- Data: pandas, openpyxl
- LLM: Groq
