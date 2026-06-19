# Kantar BrandEcho - Data Assistant

A React + Vite frontend with a FastAPI backend that mirrors the Streamlit chat application, while keeping the original `main.py` untouched.

## Architecture

```
Trial3/
├── app/
│   ├── main.py (UNCHANGED - core logic)
│   └── ...
├── api/
│   └── server.py (NEW - FastAPI backend)
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   ├── components/
│   │   │   ├── LeftSidebar.jsx & .css
│   │   │   ├── ChatArea.jsx & .css
│   │   │   ├── RightSidebar.jsx & .css
│   │   ├── utils/
│   │   │   └── api.js
│   │   ├── main.jsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── requirements.txt (UPDATED - added FastAPI, Uvicorn)
└── .env (existing)
```

## Setup Instructions

### 1. Install Backend Dependencies

```bash
# From the project root
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
cd ..
```

### 3. Run the FastAPI Backend

```bash
# From the project root
python -m api.server
# Or:
uvicorn api.server:app --reload
```

The API will start on `http://localhost:8000`

Check health: `http://localhost:8000/api/health`

### 4. Run the React Frontend (in a separate terminal)

```bash
cd frontend
npm run dev
```

The frontend will start on `http://localhost:5173`

## Features

- **Left Sidebar**: 
  - App branding (kantar / brandecho)
  - New Chat button
  - Recent chat history

- **Chat Area**:
  - Message display
  - Input box with Enter/Shift+Enter support
  - Dark/Light theme toggle
  - Loading indicator

- **Right Sidebar**:
  - Route JSON (collapsible)
  - Matched projects table (collapsible)
  - Matched factors table (collapsible)
  - Last retrieval note

## How It Works

1. **User sends a question** → React frontend receives it
2. **Frontend calls backend APIs**:
   - `POST /api/route-query` → Determines intent (project_lookup, factor_lookup, etc.)
   - `POST /api/filter-projects` → Filters database based on route
   - `POST /api/fetch-factors` → Gets related factors
   - `POST /api/answer` → Gets AI answer from Groq
3. **Backend imports functions from main.py** without modifying it
4. **Response is displayed** in chat area with retrieval details on right panel

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/health` | Check server status |
| POST | `/api/route-query` | Route user query to determine intent |
| POST | `/api/filter-projects` | Filter projects based on hints |
| POST | `/api/fetch-factors` | Get factors for projects |
| POST | `/api/answer` | Generate answer using Groq |
| GET | `/api/catalog` | Get sample data catalog |

## Environment Variables

Make sure your `.env` file has:

```
GROQ_API_KEY=your_key_here
SSL_CERT_FILE=optional_ssl_cert_path
```

## Development

### Frontend Only Changes
Edit React components in `frontend/src/components/`

### Backend Changes
Edit `api/server.py` - it imports and wraps `app/main.py` functions

### Original Logic
`app/main.py` remains **completely untouched**

## Building for Production

### Frontend Build
```bash
cd frontend
npm run build
```

Output will be in `frontend/dist/`

### Deploy Backend
```bash
# Using Gunicorn (production)
pip install gunicorn
gunicorn api.server:app -w 4 -b 0.0.0.0:8000
```

## Switching Between Streamlit and React

### To use Streamlit:
```bash
streamlit run app/main.py
```

### To use React + FastAPI:
```bash
# Terminal 1
python -m api.server

# Terminal 2
cd frontend && npm run dev
```

Both work with the same `main.py` - it's just a different frontend!

## Troubleshooting

**Frontend can't connect to API:**
- Ensure FastAPI is running on `localhost:8000`
- Check CORS settings in `api/server.py`
- Use browser DevTools → Network tab to see API calls

**Data not showing:**
- Check that Excel files exist in `data/` folder
- Verify `.env` has GROQ_API_KEY
- Check server logs for errors

**Slow responses:**
- First query will load data from Excel (cached)
- Groq API calls depend on network

## License

Same as original project
