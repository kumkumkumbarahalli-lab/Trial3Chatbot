# Data Assistant Chat App

Streamlit chat app that answers questions from two Excel sources:

- `data/Complete-DB.xlsx` (project-level data)
- `data/Factors-DB.xlsx` (factor-level data)

The app supports project lookups, factor flow lookups, follow-up questions, and clarifications when a query is ambiguous.

## Current Project Structure

```txt
Trial3/
├── app/
│   └── main.py
├── data/
│   ├── Complete-DB.xlsx
│   └── Factors-DB.xlsx
├── README.md
└── requirements.txt
```

## Setup

### 1) Create and activate a virtual environment

Windows (PowerShell):

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

### 3) Configure environment variables

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_api_key_here
# Optional: set if your network requires a custom certificate
SSL_CERT_FILE=path_to_ca_bundle
```

### 4) Run the app

```bash
streamlit run app/main.py
```

## What the App Does

1. Accepts natural language questions in chat.
2. Uses a Groq routing step to classify intent (`project_lookup`, `factor_lookup`, `follow_up`, `summary`, or `clarify`).
3. Filters matching project rows from `Complete-DB.xlsx` using hints like brand, client, market, category, subcategory, DV, and CoE job number.
4. Retrieves linked factor rows from `Factors-DB.xlsx` for factor-related questions.
5. Returns either:
- a structured factor flow response grouped by `FactorType`, or
- a Groq-generated concise answer grounded in retrieved context.

## Retrieval Trace in UI

The sidebar shows the latest retrieval debug info:

- route JSON from the router
- matched project rows
- matched factor rows
- a retrieval status note

This makes it easy to inspect what the app matched for each question.

## Behavior Notes

- Chat history is stored in Streamlit session state for follow-ups.
- Column names are trimmed and missing values are normalized to empty strings.
- If the `Factors` data has no `sequence` column, one is auto-created.
- Ambiguous brand/client and category/subcategory matches trigger clarification prompts.
- If multiple projects match a factor question, the app asks for disambiguation (for example, CoE job number).

## Requirements

Dependencies are managed in `requirements.txt`:

- `streamlit`
- `pandas`
- `openpyxl`
- `groq`
- `python-dotenv`