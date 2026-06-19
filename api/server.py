"""
FastAPI server to expose main.py logic without modifying it.
Wraps the core functions from main.py and serves them as REST APIs.
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional

import httpx
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Add parent directory to path to import main
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import functions from main.py
from app.main import (
    answer_with_groq,
    build_catalog_text,
    fetch_factors_for_projects,
    filter_projects,
    load_data,
    route_query,
)

app = FastAPI()

# Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load data once at startup
complete_df, factors_df = load_data()

API_KEY = os.getenv("GROQ_API_KEY", "")
SSL_CERT = os.getenv("SSL_CERT_FILE", False)
_http_client = httpx.Client(verify=SSL_CERT)
client = Groq(api_key=API_KEY, http_client=_http_client) if API_KEY else None


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _unique_count(df: pd.DataFrame, column: str | None) -> int:
    if not column:
        return 0
    series = df[column].astype(str).str.strip()
    series = series[series != ""]
    return int(series.nunique())


def _value_counts(df: pd.DataFrame, column: str | None, top_n: int = 10) -> list[dict]:
    if not column:
        return []
    series = df[column].astype(str).str.strip()
    series = series[series != ""]
    if series.empty:
        return []
    counts = series.value_counts().head(top_n)
    return [{"label": str(label), "count": int(count)} for label, count in counts.items()]


def _top_categories_by_brand_count(df: pd.DataFrame, category_col: str | None, brand_col: str | None, top_n: int = 10) -> list[dict]:
    if not category_col or not brand_col:
        return []

    working = df[[category_col, brand_col]].copy()
    working[category_col] = working[category_col].astype(str).str.strip()
    working[brand_col] = working[brand_col].astype(str).str.strip()
    working = working[(working[category_col] != "") & (working[brand_col] != "")]

    if working.empty:
        return []

    grouped = (
        working.drop_duplicates([category_col, brand_col])
        .groupby(category_col)[brand_col]
        .nunique()
        .sort_values(ascending=False)
        .head(top_n)
    )

    return [{"label": str(label), "count": int(count)} for label, count in grouped.items()]


def _brand_distribution_for_category(df: pd.DataFrame, category_col: str | None, brand_col: str | None, selected_category: str | None) -> tuple[str | None, list[str], list[dict]]:
    if not category_col or not brand_col:
        return None, [], []

    working = df[[category_col, brand_col]].copy()
    working[category_col] = working[category_col].astype(str).str.strip()
    working[brand_col] = working[brand_col].astype(str).str.strip()
    working = working[(working[category_col] != "") & (working[brand_col] != "")]

    if working.empty:
        return None, [], []

    category_options = sorted(working[category_col].dropna().unique().tolist())
    if not category_options:
        return None, [], []

    chosen = selected_category if selected_category in category_options else category_options[0]

    # Use all brands, no top-N cut — full distribution
    chosen_df = working[working[category_col] == chosen]
    counts = chosen_df[brand_col].value_counts()
    total = int(counts.sum())
    data = [
        {
            "label": str(label),
            "count": int(count),
            "percentage": round((int(count) / total * 100), 1) if total else 0,
        }
        for label, count in counts.items()
    ]

    return chosen, category_options, data


# Pydantic Models
class QueryRequest(BaseModel):
    question: str
    history: Optional[list] = None


class RouteRequest(BaseModel):
    question: str
    history: Optional[list] = None


class FilterProjectsRequest(BaseModel):
    intent: str
    brand_hint: Optional[str] = None
    client_hint: Optional[str] = None
    market_hint: Optional[str] = None
    category_hint: Optional[str] = None
    subcategory_hint: Optional[str] = None
    dependent_var_hint: Optional[str] = None
    factor_type_hint: Optional[str] = None
    coe_job_number_hint: Optional[str] = None
    brand_client_scope: Optional[str] = None
    category_scope: Optional[str] = None
    needs_followup_context: Optional[bool] = False
    clarification_question: Optional[str] = None


class FactorsRequest(BaseModel):
    projects: list
    route: dict


class AnswerRequest(BaseModel):
    question: str
    route: dict
    project_rows: list
    factor_rows: list


# API Endpoints
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "api_key_present": bool(API_KEY)}


@app.post("/api/route-query")
async def api_route_query(request: RouteRequest):
    """Route a query to determine intent and required filters."""
    history = request.history or []
    route = route_query(request.question, history)
    return route


@app.post("/api/filter-projects")
async def api_filter_projects(route: FilterProjectsRequest):
    """Filter projects based on route hints."""
    candidates, clarify_msg = filter_projects(route.model_dump())
    return {
        "projects": candidates.to_dict(orient="records"),
        "clarification_message": clarify_msg,
        "row_count": len(candidates),
    }


@app.post("/api/fetch-factors")
async def api_fetch_factors(request: FactorsRequest):
    """Fetch factors for the given projects."""
    if not request.projects:
        return {"factors": [], "row_count": 0}
    
    df = pd.DataFrame(request.projects)
    factors = fetch_factors_for_projects(df, request.route)
    return {
        "factors": factors.to_dict(orient="records"),
        "row_count": len(factors),
    }


@app.post("/api/answer")
async def api_answer(request: AnswerRequest):
    """Get answer from Groq based on context."""
    if not client:
        return {"answer": "GROQ_API_KEY is missing."}
    
    project_df = pd.DataFrame(request.project_rows) if request.project_rows else pd.DataFrame()
    factor_df = pd.DataFrame(request.factor_rows) if request.factor_rows else pd.DataFrame()
    
    answer = answer_with_groq(request.question, request.route, project_df, factor_df)
    return {"answer": answer}


@app.get("/api/catalog")
async def api_catalog():
    """Get sample data catalog."""
    catalog = build_catalog_text()
    return {"catalog": json.loads(catalog)}


@app.get("/api/dashboard-summary")
async def api_dashboard_summary(selected_category: Optional[str] = None):
    """Return KPI tiles and chart series for the dashboard page."""
    category_col = _pick_column(complete_df, ["Category"])
    subcategory_col = _pick_column(complete_df, ["SubCategory"])
    client_col = _pick_column(complete_df, ["Client", "ClientName"])
    brand_col = _pick_column(complete_df, ["BrandModelled"])
    market_col = _pick_column(complete_df, ["MarketforBrand", "Market", "Country"])

    chosen_category, category_options, brand_distribution = _brand_distribution_for_category(
        complete_df,
        category_col,
        brand_col,
        selected_category,
    )

    return {
        "kpis": {
            "total_records": int(len(complete_df)),
            "unique_categories": _unique_count(complete_df, category_col),
            "unique_subcategories": _unique_count(complete_df, subcategory_col),
            "unique_clients": _unique_count(complete_df, client_col),
            "unique_brands": _unique_count(complete_df, brand_col),
            "unique_markets": _unique_count(complete_df, market_col),
        },
        "charts": {
            "brand_distribution_for_selected_category": brand_distribution,
            "top_categories_by_brand_count": _top_categories_by_brand_count(complete_df, category_col, brand_col, top_n=9999),
            "top_markets": _value_counts(complete_df, market_col, top_n=10),
            "all_markets": _value_counts(complete_df, market_col, top_n=9999),
            "top_brands": _value_counts(complete_df, brand_col, top_n=10),
        },
        "slicers": {
            "selected_category": chosen_category,
            "category_options": category_options,
            "market_options": sorted(
                complete_df[market_col].dropna().astype(str).str.strip()
                .replace("", pd.NA).dropna().unique().tolist()
            ) if market_col else [],
        },
    }


@app.get("/api/market-breakdown")
async def api_market_breakdown(market: Optional[str] = None):
    """Return category/subcategory and brand breakdown for a selected market."""
    market_col = _pick_column(complete_df, ["MarketforBrand", "Market", "Country"])
    category_col = _pick_column(complete_df, ["Category"])
    subcategory_col = _pick_column(complete_df, ["SubCategory"])
    brand_col = _pick_column(complete_df, ["BrandModelled"])

    if not market_col:
        return {"selected_market": None, "categories_subcategories": [], "brands": []}

    markets_series = complete_df[market_col].astype(str).str.strip()
    market_options = sorted(markets_series[markets_series != ""].unique().tolist())

    selected_market = market if market in market_options else (market_options[0] if market_options else None)
    if not selected_market:
        return {"selected_market": None, "categories_subcategories": [], "brands": []}

    market_df = complete_df[complete_df[market_col].astype(str).str.strip() == selected_market]

    # Category × Subcategory breakdown
    cat_subcat: list[dict] = []
    if category_col and subcategory_col:
        grp = (
            market_df.groupby([category_col, subcategory_col])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
        )
        cat_subcat = [
            {"category": str(r[category_col]), "subcategory": str(r[subcategory_col]), "count": int(r["count"])}
            for _, r in grp.iterrows()
            if str(r[category_col]).strip() and str(r[subcategory_col]).strip()
        ]

    brands = _value_counts(market_df, brand_col, top_n=9999)

    return {
        "selected_market": selected_market,
        "categories_subcategories": cat_subcat,
        "brands": brands,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
