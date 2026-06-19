# Kantar BrandEcho — Data Assistant

A full-stack AI-powered chat and analytics application for exploring brand research data across two Excel databases.

- `data/Complete-DB.xlsx` — 812 project-level records (brands, categories, markets, clients)
- `data/Factors-DB.xlsx` — factor-level rows linked to projects (factor types, weights, sequences)

The app combines a **React frontend** with a **FastAPI backend** and uses the **Groq LLM** (llama-3.3-70b-versatile) for natural language routing and answers.

---

## Project Structure

```
Trial3/
├── api/
│   └── server.py           # FastAPI backend — all API endpoints
├── app/
│   └── main.py             # Original Streamlit app (logic reference)
├── data/
│   ├── Complete-DB.xlsx    # 812 project records
│   └── Factors-DB.xlsx     # Factor rows
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx         # Root component — state & API orchestration
│       ├── main.jsx
│       ├── App.css
│       ├── index.css
│       ├── components/
│       │   ├── ChatArea.jsx / .css
│       │   ├── LeftSidebar.jsx / .css
│       │   ├── RightSidebar.jsx / .css
│       │   ├── DashboardView.jsx / .css
│       │   ├── WorldMap.jsx / .css
│       │   └── MarketCards.jsx / .css
│       └── utils/
│           └── api.js      # Fetch helper
├── requirements.txt
├── REACT_SETUP.md
└── README.md
```

---

## Features

### Chat Interface
- Natural language questions answered using **Groq LLM** (llama-3.3-70b-versatile)
- Intent routing: `project_lookup`, `factor_lookup`, `follow_up`, `summary`, `clarify`
- Filters projects by brand, client, market, category, subcategory, DV, CoE job number
- Retrieves linked factor rows for factor-related questions
- Structured factor flow response grouped by `FactorType`
- Disambiguation prompts for ambiguous brand/client or multi-project matches
- Chat history preserved for follow-up questions

### Retrieval Sidebar (right panel)
- Shows the latest retrieval trace per question:
  - Matched project rows (all DB columns, dynamic)
  - Matched factor rows (sequence column hidden)
  - Route JSON from the LLM router
  - Retrieval status note
- Resizable panel with drag handle

### Dashboard View
Accessible via the bar-chart button in the left sidebar.

**KPI Tiles** (6 cards):
- Total Records, Unique Categories, Unique Subcategories, Unique Clients, Unique Brands, Unique Markets

**Bar Chart — Top Categories by Number of Brands**
- Shows top 10 categories ranked by distinct brand count
- Toggle button switches between raw counts and correct percentages (denominator = all 22 categories, not just visible top 10)

**Donut Chart — Distribution of Brands by Category**
- Category slicer (dropdown) to select any category
- Shows all brands for that category as a conic-gradient donut
- Legend shows count + percentage for each brand
- Center displays total project count for the selected category
- 20-color palette for up to 104+ brands

**World Map — Brand Presence Across Markets**
- Filled choropleth map: countries colored light→dark blue by project count
- Covers all 94 markets from the database
- Click any highlighted country to select it as the active market
- Market slicer (top-right of map) with all 94 options — also zooms to selected country
- Scroll-wheel zoom and drag pan supported
- Gradient scale legend

**Market Breakdown Cards** (appear after selecting a market)
- Left card: Category × Subcategory combinations for the selected market (with project counts)
- Right card: All brands present in the selected market (with project counts)

---

## Setup

### 1. Create and activate a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
# Optional: custom certificate if required by your network
SSL_CERT_FILE=path_to_ca_bundle
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
```

### 5. Build the frontend

```bash
cd frontend
npm run build
```

---

## Running the App

### Start the backend (FastAPI)

From the project root, with the virtual environment active:

```powershell
.venv\Scripts\python.exe -m api.server
```

The API will be available at `http://localhost:8000`.

### Start the frontend (development)

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` in your browser.

> For production, `npm run build` outputs to `frontend/dist/` which can be served statically.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/route` | Route a question (returns intent + filters) |
| `POST` | `/api/filter-projects` | Filter projects from Complete-DB |
| `POST` | `/api/fetch-factors` | Fetch factor rows for matched projects |
| `POST` | `/api/answer` | Generate LLM answer from context |
| `GET`  | `/api/dashboard-summary` | KPIs, charts, slicers for the dashboard |
| `GET`  | `/api/market-breakdown` | Category/subcategory & brand breakdown for a market |
| `GET`  | `/api/catalog` | Data catalog summary |

---

## Data Rules

- **All KPIs and chart metrics** (categories, brands, markets, clients) are derived from `Complete-DB.xlsx`
- **Factor type distribution** is derived from `Factors-DB.xlsx` only
- Brand distribution percentages are computed against the full dataset (no top-N truncation)

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, CSS modules |
| Maps | react-simple-maps, world-atlas |
| Backend | Python, FastAPI, Uvicorn |
| Data | pandas, openpyxl |
| LLM | Groq API (llama-3.3-70b-versatile) |
| Original app | Streamlit (app/main.py) |

---

## Requirements

Key Python dependencies (see `requirements.txt` for full list):

- `fastapi`, `uvicorn`
- `pandas`, `openpyxl`
- `groq`
- `python-dotenv`
- `streamlit` (for the original app/main.py reference)
