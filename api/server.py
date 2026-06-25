"""
FastAPI server to expose main.py logic without modifying it.
Wraps the core functions from main.py and serves them as REST APIs.
"""
import json
import os
import re
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
    compute_aggregation_stats,
    factor_project_options,
    filter_factors_directly,
    fetch_factors_for_projects,
    filter_projects,
    load_data,
    merge_followup_route,
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

MULTI_VALUE_COLUMNS = {
    "BrandModelled",
    "MarketforBrand",
    "Client",
    "ClientName",
    "Market",
    "Country",
}


def _norm_text(value: str) -> str:
    return "".join(ch for ch in _safe_str(value).lower() if ch.isalnum())


def _split_cell_values(value: str) -> list[str]:
    raw = _safe_str(value)
    if not raw:
        return []
    normalized = raw.replace(";", ",")
    return [part.strip() for part in normalized.split(",") if part.strip()]


def _series_for_counts(df: pd.DataFrame, column: str | None) -> pd.Series:
    if not column:
        return pd.Series(dtype="object")
    series = df[column].astype(str).str.strip()
    series = series[series != ""]

    if column in MULTI_VALUE_COLUMNS:
        series = series.apply(_split_cell_values).explode().dropna()
        series = series.astype(str).str.strip()
        series = series[series != ""]

    return series


def _cell_matches_hint(cell_value: str, hint_value: str, is_multi_value: bool) -> bool:
    needle = _norm_text(hint_value)
    if not needle:
        return False

    if is_multi_value:
        tokens = [_norm_text(token) for token in _split_cell_values(cell_value)]
        tokens = [token for token in tokens if token]

        if len(needle) < 3:
            return needle in tokens

        return any(token == needle or needle in token or token in needle for token in tokens)

    hay = _norm_text(cell_value)
    if len(needle) < 3:
        return hay == needle
    return needle in hay


def _pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _unique_count(df: pd.DataFrame, column: str | None) -> int:
    series = _series_for_counts(df, column)
    if series.empty:
        return 0
    return int(series.nunique())


def _value_counts(df: pd.DataFrame, column: str | None, top_n: int = 10) -> list[dict]:
    series = _series_for_counts(df, column)
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

    if brand_col in MULTI_VALUE_COLUMNS:
        working[brand_col] = working[brand_col].apply(_split_cell_values)
        working = working.explode(brand_col)
        working[brand_col] = working[brand_col].astype(str).str.strip()
        working = working[working[brand_col] != ""]

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

    if brand_col in MULTI_VALUE_COLUMNS:
        chosen_df = chosen_df.copy()
        chosen_df[brand_col] = chosen_df[brand_col].apply(_split_cell_values)
        chosen_df = chosen_df.explode(brand_col)
        chosen_df[brand_col] = chosen_df[brand_col].astype(str).str.strip()
        chosen_df = chosen_df[chosen_df[brand_col] != ""]

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
    route_history: Optional[list] = None


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


class AnalyticsAnswerRequest(BaseModel):
    question: str
    route: dict


def _safe_str(value) -> str:
    return "" if value is None else str(value).strip()


def _is_count_style_question(question: str) -> bool:
    q = _safe_str(question).lower()
    return any(token in q for token in ["how many", "count", "number of", "total"])


def _is_affirmative_followup(question: str) -> bool:
    q = _safe_str(question).lower().strip(" .!?")
    return q in {
        "yes",
        "yeah",
        "yep",
        "sure",
        "ok",
        "okay",
        "go ahead",
        "please do",
        "show me",
    }


def _extract_value_with_patterns(question: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, question, flags=re.IGNORECASE)
        if not match:
            continue
        value = _safe_str(match.group(1)).strip(" .,!?:;\"'")
        if value:
            return value
    return None


def _normalize_route_with_question(question: str, route: dict) -> dict:
    normalized = (route or {}).copy()
    q = _safe_str(question)
    q_lower = q.lower()

    has_subcategory_word = bool(re.search(r"\bsub\s*categor(?:y|ies)\b", q_lower))
    has_category_word = bool(re.search(r"\bcategor(?:y|ies)\b", q_lower))
    asks_for_dependent_variable = bool(
        re.search(r"\b(what|which)\b.*\bdependent\s*(variable|var|dv)\b", q_lower)
    )
    is_affirmative = _is_affirmative_followup(q)
    looks_analytics = bool(
        re.search(
            r"\b(how many|count|number of|top|most|least|fewest|highest|lowest|compare|max|min|unique|per|within each)\b",
            q_lower,
        )
    )

    # Decide scope explicitly from user phrasing to avoid Category/SubCategory ambiguity.
    if has_subcategory_word:
        normalized["category_scope"] = "subcategory"
    elif has_category_word:
        normalized["category_scope"] = "category"

    # Recover missing category hints from common phrasings like "food category".
    category_hint = _safe_str(normalized.get("category_hint"))
    subcategory_hint = _safe_str(normalized.get("subcategory_hint"))

    if not category_hint:
        extracted_category = _extract_value_with_patterns(
            q,
            [
                r"\bin\s+([a-zA-Z0-9&/\-\s]+?)\s+category\b",
                r"\bfor\s+category\s+([a-zA-Z0-9&/\-\s]+?)\b",
                r"\bcategory\s*[:\-]?\s*([a-zA-Z0-9&/\-\s]+?)\b(?:$|[?.!,])",
            ],
        )
        if extracted_category and extracted_category.lower() not in ["category", "subcategory", "subcategories"]:
            normalized["category_hint"] = extracted_category

    # If user asks about subcategories "in X" (without explicitly saying "X category"),
    # treat X as a category constraint.
    if has_subcategory_word and not _safe_str(normalized.get("category_hint")):
        inferred_category = _extract_value_with_patterns(
            q,
            [
                r"\bare\s+there\s+in\s+([a-zA-Z0-9&/\-\s]+?)\b(?:$|[?.!,])",
                r"\bin\s+([a-zA-Z0-9&/\-\s]+?)\b(?:$|[?.!,])",
            ],
        )
        if inferred_category and inferred_category.lower() not in ["category", "subcategory", "subcategories"]:
            normalized["category_hint"] = inferred_category
            normalized["category_scope"] = "category"

    if not subcategory_hint and has_subcategory_word and _safe_str(normalized.get("category_scope")) == "subcategory":
        extracted_subcategory = _extract_value_with_patterns(
            q,
            [
                r"\bsub\s*category\s*[:\-]?\s*([a-zA-Z0-9&/\-\s]+?)\b(?:$|[?.!,])",
                r"\bsubcategories\s+for\s+([a-zA-Z0-9&/\-\s]+?)\b",
            ],
        )
        if extracted_subcategory:
            normalized["subcategory_hint"] = extracted_subcategory

    # Keep rank-style questions in analytics even if intent was misclassified.
    analytics_type = _safe_str(normalized.get("analytics_type")).lower()
    if analytics_type and any(token in analytics_type for token in ["top", "most", "least", "frequent"]):
        normalized["intent"] = "analytics"
    elif _safe_str(normalized.get("intent")).lower() == "analytics":
        # Non-ranking "how many" queries are better handled via filtered project lookup.
        normalized["intent"] = "project_lookup"

    if looks_analytics and not is_affirmative and not asks_for_dependent_variable:
        normalized["intent"] = "analytics"

    # For count-style scoped questions, ensure we don't fall back to clarify when filters exist.
    if _is_count_style_question(q) and _safe_str(normalized.get("intent")).lower() == "clarify":
        has_any_filter = any(
            _safe_str(normalized.get(key))
            for key in [
                "brand_hint",
                "client_hint",
                "market_hint",
                "category_hint",
                "subcategory_hint",
                "dependent_var_hint",
                "coe_job_number_hint",
            ]
        )
        if has_any_filter:
            normalized["intent"] = "project_lookup"

    # If the user asks "what/which dependent variable ...", dependent_var_hint should not
    # be treated as a filter. It is usually the requested output field.
    if asks_for_dependent_variable and _safe_str(normalized.get("dependent_var_hint")):
        normalized["dependent_var_hint"] = None

    # If user replies with a short affirmation after being asked about factors,
    # do not keep inherited factor-type constraints like "drivers".
    if is_affirmative and _safe_str(normalized.get("intent")).lower() == "factor_lookup":
        normalized["factor_type_hint"] = None

    return normalized


def _check_project_has_factors(brand: str, market: str) -> bool:
    if factors_df.empty:
        return False

    mask = pd.Series(True, index=factors_df.index)

    if "BrandModelled" in factors_df.columns and _safe_str(brand):
        mask &= _contains_ci_with_col(factors_df["BrandModelled"], brand, "BrandModelled")

    if "MarketforBrand" in factors_df.columns and _safe_str(market):
        mask &= _contains_ci_with_col(factors_df["MarketforBrand"], market, "MarketforBrand")

    return bool(mask.any())


def _pick_first_available(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _contains_ci(series: pd.Series, value: str) -> pd.Series:
    needle = _safe_str(value)
    if not needle:
        return pd.Series(False, index=series.index)
    return series.astype(str).apply(lambda cell: _cell_matches_hint(cell, needle, False))


def _contains_ci_with_col(series: pd.Series, value: str, column_name: str | None) -> pd.Series:
    needle = _safe_str(value)
    if not needle:
        return pd.Series(False, index=series.index)
    is_multi = bool(column_name and column_name in MULTI_VALUE_COLUMNS)
    return series.astype(str).apply(lambda cell: _cell_matches_hint(cell, needle, is_multi))


def _apply_route_filters(df: pd.DataFrame, route: dict) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    mask = pd.Series(True, index=out.index)

    col_map = {
        "brand_hint": _pick_first_available(out, ["BrandModelled"]),
        "client_hint": _pick_first_available(out, ["Client", "ClientName"]),
        "market_hint": _pick_first_available(out, ["MarketforBrand", "Market", "Country"]),
        "category_hint": _pick_first_available(out, ["Category"]),
        "subcategory_hint": _pick_first_available(out, ["SubCategory"]),
        "dependent_var_hint": _pick_first_available(out, ["Dependentvar"]),
        "factor_type_hint": _pick_first_available(out, ["FactorType"]),
    }

    for hint_key, col in col_map.items():
        hint_value = _safe_str((route or {}).get(hint_key))
        if col and hint_value:
            mask &= _contains_ci_with_col(out[col], hint_value, col)

    return out[mask].copy()


def _format_ranked_counts(series: pd.Series, heading: str, limit: int = 10) -> str:
    if series is None or series.empty:
        return "No data found for that query."

    lines = [heading]
    for idx, (label, count) in enumerate(series.head(limit).items(), start=1):
        lines.append(f"{idx}. {label}: {int(count)}")
    return "\n".join(lines)


def _deterministic_analytics_answer(question: str, route: dict) -> tuple[str | None, list[dict]]:
    q = _safe_str(question).lower()
    route = route or {}

    project_df = _apply_route_filters(complete_df.copy(), route)
    factor_df = _apply_route_filters(factors_df.copy(), route)

    brand_col = _pick_first_available(project_df, ["BrandModelled"])
    client_col = _pick_first_available(project_df, ["Client", "ClientName"])
    market_col = _pick_first_available(project_df, ["MarketforBrand", "Market", "Country"])
    category_col = _pick_first_available(project_df, ["Category"])
    subcategory_col = _pick_first_available(project_df, ["SubCategory"])
    dep_col = _pick_first_available(project_df, ["Dependentvar"])
    factor_type_col = _pick_first_available(factor_df, ["FactorType"])
    factor_name_col = _pick_first_available(factor_df, ["FactorName"])

    def sample_records(df: pd.DataFrame) -> list[dict]:
        return df.head(100).to_dict(orient="records") if not df.empty else []

    # Basic counts
    if "how many projects" in q and ("total" in q or "in total" in q or "overall" in q):
        return (f"Total projects: {len(project_df)}", sample_records(project_df))
    if "how many categories" in q and category_col:
        value = int(project_df[category_col].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        return (f"Unique categories: {value}", sample_records(project_df))
    if ("how many unique clients" in q or "number of unique clients" in q) and client_col:
        value = int(project_df[client_col].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
        return (f"Unique clients: {value}", sample_records(project_df))
    if ("how many markets" in q or "markets are covered" in q or "unique markets" in q) and market_col:
        markets = (
            project_df[market_col].astype(str).str.strip().replace("", pd.NA).dropna().drop_duplicates().tolist()
        )
        lines = [f"I found {len(markets)} markets.", "Markets:"]
        lines.extend([f"- {m}" for m in markets])
        return ("\n".join(lines), sample_records(project_df))

    # Grouped counts
    if ("per category" in q or "within each category" in q) and category_col:
        if ("records" in q or "projects" in q) and "subcategory" not in q:
            counts = project_df[category_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
            return (_format_ranked_counts(counts, "Records per category:"), sample_records(project_df))
        if "subcategory" in q and subcategory_col:
            grouped = (
                project_df[[category_col, subcategory_col]]
                .astype(str)
                .apply(lambda c: c.str.strip())
                .replace("", pd.NA)
                .dropna()
                .drop_duplicates()
                .groupby(category_col)[subcategory_col]
                .nunique()
                .sort_values(ascending=False)
            )
            return (_format_ranked_counts(grouped, "Unique subcategories within each category:"), sample_records(project_df))
    if ("brands per client" in q or "count of brands per client" in q) and client_col and brand_col:
        grouped = (
            project_df[[client_col, brand_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(client_col)[brand_col]
            .nunique()
            .sort_values(ascending=False)
        )
        return (_format_ranked_counts(grouped, "Unique brands per client:"), sample_records(project_df))

    # Distinct counts
    if ("unique brands per category" in q or "number of unique brands per category" in q) and category_col and brand_col:
        grouped = (
            project_df[[category_col, brand_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(category_col)[brand_col]
            .nunique()
            .sort_values(ascending=False)
        )
        return (_format_ranked_counts(grouped, "Unique brands per category:"), sample_records(project_df))
    if ("unique markets per client" in q or "number of unique markets per client" in q) and client_col and market_col:
        grouped = (
            project_df[[client_col, market_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(client_col)[market_col]
            .nunique()
            .sort_values(ascending=False)
        )
        return (_format_ranked_counts(grouped, "Unique markets per client:"), sample_records(project_df))

    # Top/least single-dimension
    if category_col and ("most" in q or "least" in q or "fewest" in q):
        if "category" in q:
            counts = project_df[category_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
            if not counts.empty:
                if "least" in q or "fewest" in q:
                    label, value = counts.sort_values(ascending=True).index[0], int(counts.sort_values(ascending=True).iloc[0])
                    return (f"Category with the least records: {label} ({value})", sample_records(project_df))
                label, value = counts.index[0], int(counts.iloc[0])
                return (f"Category with the most records: {label} ({value})", sample_records(project_df))
    if client_col and ("client appears the most" in q or "client appears the least" in q):
        counts = project_df[client_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if not counts.empty:
            if "least" in q:
                counts = counts.sort_values(ascending=True)
            label, value = counts.index[0], int(counts.iloc[0])
            prefix = "least" if "least" in q else "most"
            return (f"Client that appears the {prefix}: {label} ({value})", sample_records(project_df))
    if market_col and ("market has the highest" in q or "market has the fewest" in q or "market has the least" in q):
        counts = project_df[market_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if not counts.empty:
            if "least" in q or "fewest" in q:
                counts = counts.sort_values(ascending=True)
            label, value = counts.index[0], int(counts.iloc[0])
            word = "lowest" if ("least" in q or "fewest" in q) else "highest"
            return (f"Market with the {word} number of projects: {label} ({value})", sample_records(project_df))
    if brand_col and ("brand is modeled the most" in q or "brand appears only once" in q):
        counts = project_df[brand_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if not counts.empty:
            if "only once" in q:
                singles = counts[counts == 1]
                if singles.empty:
                    return ("No brands appear only once.", sample_records(project_df))
                lines = [f"Brands appearing only once: {len(singles)}", "Brands:"]
                lines.extend([f"- {name}" for name in singles.index.tolist()[:50]])
                return ("\n".join(lines), sample_records(project_df))
            label, value = counts.index[0], int(counts.iloc[0])
            return (f"Most modeled brand: {label} ({value})", sample_records(project_df))

    # Ranked lists
    if "top" in q and client_col and "client" in q and "project" in q:
        limit = 10 if "top 10" in q else 5 if "top 5" in q else 10
        counts = project_df[client_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        return (_format_ranked_counts(counts, "Top clients by number of projects:", limit=limit), sample_records(project_df))
    if "top" in q and market_col and "market" in q and ("count of brands" in q or "brands" in q):
        limit = 10 if "top 10" in q else 5 if "top 5" in q else 10
        grouped = (
            project_df[[market_col, brand_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(market_col)[brand_col]
            .nunique()
            .sort_values(ascending=False)
        )
        return (_format_ranked_counts(grouped, "Top markets by count of brands:", limit=limit), sample_records(project_df))

    # Multi-level top
    if "top client within each category" in q and category_col and client_col:
        tmp = (
            project_df[[category_col, client_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .groupby([category_col, client_col])
            .size()
            .reset_index(name="count")
            .sort_values([category_col, "count"], ascending=[True, False])
        )
        top_each = tmp.groupby(category_col).head(1)
        lines = ["Top client within each category:"]
        for _, row in top_each.iterrows():
            lines.append(f"- {row[category_col]}: {row[client_col]} ({int(row['count'])})")
        return ("\n".join(lines), sample_records(project_df))
    if "top market within each category" in q and category_col and market_col:
        tmp = (
            project_df[[category_col, market_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .groupby([category_col, market_col])
            .size()
            .reset_index(name="count")
            .sort_values([category_col, "count"], ascending=[True, False])
        )
        top_each = tmp.groupby(category_col).head(1)
        lines = ["Top market within each category:"]
        for _, row in top_each.iterrows():
            lines.append(f"- {row[category_col]}: {row[market_col]} ({int(row['count'])})")
        return ("\n".join(lines), sample_records(project_df))
    if "top subcategory" in q and subcategory_col and category_col:
        filtered = project_df
        category_hint = _safe_str(route.get("category_hint"))
        if category_hint:
            filtered = filtered[_contains_ci(filtered[category_col], category_hint)]
        counts = filtered[subcategory_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if not counts.empty:
            return (f"Top subcategory: {counts.index[0]} ({int(counts.iloc[0])})", sample_records(filtered))

    # Comparative and advanced
    if "compare top vs least categories" in q and category_col:
        counts = project_df[category_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if not counts.empty:
            top_label, top_count = counts.index[0], int(counts.iloc[0])
            low_label, low_count = counts.sort_values(ascending=True).index[0], int(counts.sort_values(ascending=True).iloc[0])
            return (
                f"Top category: {top_label} ({top_count})\nLeast category: {low_label} ({low_count})\nGap: {top_count - low_count}",
                sample_records(project_df),
            )
    if "highest vs lowest brand count" in q and market_col and brand_col:
        grouped = (
            project_df[[market_col, brand_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(market_col)[brand_col]
            .nunique()
        )
        if not grouped.empty:
            high_mkt, high_count = grouped.idxmax(), int(grouped.max())
            low_mkt, low_count = grouped.idxmin(), int(grouped.min())
            return (
                f"Highest brand-count market: {high_mkt} ({high_count})\nLowest brand-count market: {low_mkt} ({low_count})",
                sample_records(project_df),
            )
    if "max and min presence across categories" in q and client_col and category_col:
        grouped = (
            project_df[[client_col, category_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(client_col)[category_col]
            .nunique()
        )
        if not grouped.empty:
            max_client, max_count = grouped.idxmax(), int(grouped.max())
            min_client, min_count = grouped.idxmin(), int(grouped.min())
            return (
                f"Max category presence client: {max_client} ({max_count})\nMin category presence client: {min_client} ({min_count})",
                sample_records(project_df),
            )
    if "only 1 client exists" in q and category_col and client_col:
        grouped = (
            project_df[[category_col, client_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(category_col)[client_col]
            .nunique()
        )
        one_client = grouped[grouped == 1]
        if one_client.empty:
            return ("No categories have only one client.", sample_records(project_df))
        lines = [f"Categories with only 1 client: {len(one_client)}", "Categories:"]
        lines.extend([f"- {name}" for name in one_client.index.tolist()])
        return ("\n".join(lines), sample_records(project_df))
    if "client operates in maximum number of markets" in q and client_col and market_col:
        grouped = (
            project_df[[client_col, market_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(client_col)[market_col]
            .nunique()
        )
        if not grouped.empty:
            name, value = grouped.idxmax(), int(grouped.max())
            return (f"Client with maximum markets: {name} ({value})", sample_records(project_df))
    if "brands are most diversified across markets" in q and brand_col and market_col:
        grouped = (
            project_df[[brand_col, market_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .drop_duplicates()
            .groupby(brand_col)[market_col]
            .nunique()
            .sort_values(ascending=False)
        )
        return (_format_ranked_counts(grouped, "Brands diversified across markets:"), sample_records(project_df))
    if "highest concentration in one market" in q and category_col and market_col:
        tmp = (
            project_df[[category_col, market_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .groupby([category_col, market_col])
            .size()
            .reset_index(name="count")
        )
        if not tmp.empty:
            concentration_rows = []
            for cat, grp in tmp.groupby(category_col):
                total = grp["count"].sum()
                top_count = int(grp["count"].max())
                top_market = grp.sort_values("count", ascending=False).iloc[0][market_col]
                share = (top_count / total) if total else 0
                concentration_rows.append((cat, top_market, top_count, total, share))
            concentration_rows.sort(key=lambda x: x[4], reverse=True)
            cat, mkt, top_count, total, share = concentration_rows[0]
            return (
                f"Category with highest concentration in one market: {cat}\nTop market: {mkt} ({top_count}/{int(total)} = {round(share * 100, 1)}%)",
                sample_records(project_df),
            )
    if "most uneven distribution" in q and category_col and market_col:
        tmp = (
            project_df[[category_col, market_col]]
            .astype(str)
            .apply(lambda c: c.str.strip())
            .replace("", pd.NA)
            .dropna()
            .groupby([category_col, market_col])
            .size()
            .reset_index(name="count")
        )
        if not tmp.empty:
            gaps = []
            for cat, grp in tmp.groupby(category_col):
                gap = int(grp["count"].max() - grp["count"].min())
                gaps.append((cat, gap))
            gaps.sort(key=lambda x: x[1], reverse=True)
            return (f"Category with most uneven distribution: {gaps[0][0]} (gap {gaps[0][1]})", sample_records(project_df))

    # Factor analytics
    if factor_type_col and ("factortype appears most" in q or "least used factortype" in q):
        counts = factor_df[factor_type_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if not counts.empty:
            if "least" in q:
                counts = counts.sort_values(ascending=True)
                return (f"Least used FactorType: {counts.index[0]} ({int(counts.iloc[0])})", sample_records(factor_df))
            return (f"Most common FactorType: {counts.index[0]} ({int(counts.iloc[0])})", sample_records(factor_df))
    if factor_name_col and ("most common factorname" in q or "less common factornames" in q):
        counts = factor_df[factor_name_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        if counts.empty:
            return ("No factor names found for that query.", sample_records(factor_df))
        if "less common" in q:
            counts = counts.sort_values(ascending=True)
            return (_format_ranked_counts(counts, "Less common FactorNames:"), sample_records(factor_df))
        return (_format_ranked_counts(counts, "Most common FactorNames:"), sample_records(factor_df))
    if factor_type_col and factor_name_col and "top emotional factors" in q:
        emotional = factor_df[_contains_ci(factor_df[factor_type_col], "emotional")]
        if emotional.empty:
            return ("No emotional factors found for that query.", sample_records(factor_df))
        counts = emotional[factor_name_col].astype(str).str.strip().replace("", pd.NA).dropna().value_counts()
        return (_format_ranked_counts(counts, "Top emotional factors across brands:"), sample_records(emotional))

    return (None, [])


def _normalize_text(value: str) -> str:
    return "".join(ch for ch in _safe_str(value).lower() if ch.isalnum())


def _contains_value(series: pd.Series, hint: str) -> pd.Series:
    needle = _normalize_text(hint)
    if not needle:
        return pd.Series(False, index=series.index)
    return series.astype(str).apply(lambda x: needle in _normalize_text(x))


def _apply_route_filters_to_df(df: pd.DataFrame, route: dict) -> pd.DataFrame:
    filtered = df.copy()
    mask = pd.Series(True, index=filtered.index)

    mapping = {
        "brand_hint": "BrandModelled",
        "client_hint": "Client",
        "market_hint": "MarketforBrand",
        "category_hint": "Category",
        "subcategory_hint": "SubCategory",
        "dependent_var_hint": "Dependentvar",
        "coe_job_number_hint": "CoEJobnumber",
    }

    for route_key, col in mapping.items():
        hint = _safe_str(route.get(route_key))
        if hint and col in filtered.columns:
            mask &= _contains_value(filtered[col].astype(str), hint)

    return filtered[mask].copy()


def _extract_top_n(question: str, default: int = 10) -> int:
    match = re.search(r"\b(?:top|least)\s+(\d+)\b", _safe_str(question).lower())
    if not match:
        return default
    try:
        return max(1, int(match.group(1)))
    except Exception:
        return default


def _series_counts(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=int)
    series = df[col].astype(str).str.strip()
    series = series[series != ""]
    return series.value_counts()


def _nunique_by(df: pd.DataFrame, by_col: str, value_col: str) -> pd.Series:
    if by_col not in df.columns or value_col not in df.columns:
        return pd.Series(dtype=int)
    working = df[[by_col, value_col]].copy()
    working[by_col] = working[by_col].astype(str).str.strip()
    working[value_col] = working[value_col].astype(str).str.strip()
    working = working[(working[by_col] != "") & (working[value_col] != "")]
    if working.empty:
        return pd.Series(dtype=int)
    return working.drop_duplicates([by_col, value_col]).groupby(by_col)[value_col].nunique().sort_values(ascending=False)


_DIMENSION_PATTERNS = {
    "category": r"\bcategor(?:y|ies)\b",
    "subcategory": r"\bsub[\s-]*categor(?:y|ies)\b",
    "brand": r"\bbrand(?:s)?\b",
    "client": r"\bclient(?:s)?\b",
    "market": r"\b(?:market|markets|country|countries)\b",
    "dependent_var": r"\b(?:dependent\s*var(?:iable)?s?|dvs?|dependentvar)\b",
    "project": r"\b(?:project|projects|record|records|row|rows)\b",
}

_DIMENSION_COLUMNS = {
    "category": "Category",
    "subcategory": "SubCategory",
    "brand": "BrandModelled",
    "client": "Client",
    "market": "MarketforBrand",
    "dependent_var": "Dependentvar",
    "project": None,
}

_DIMENSION_LABELS = {
    "category": "categories",
    "subcategory": "subcategories",
    "brand": "brands",
    "client": "clients",
    "market": "markets",
    "dependent_var": "dependent variables",
    "project": "projects",
}


def _find_dimension_mentions(text: str) -> list[str]:
    hits: list[tuple[int, str]] = []
    for dim, pattern in _DIMENSION_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            hits.append((match.start(), dim))

    ordered = []
    seen = set()
    for _, dim in sorted(hits, key=lambda x: x[0]):
        if dim not in seen:
            seen.add(dim)
            ordered.append(dim)
    return ordered


def _resolve_rank_dimensions(question_text: str) -> tuple[str | None, str | None]:
    group_dim = None
    metric_dim = None
    all_dims = _find_dimension_mentions(question_text)

    by_match = re.search(r"\bby\b", question_text)
    if by_match:
        before = question_text[: by_match.start()]
        after = question_text[by_match.end() :]
        before_dims = _find_dimension_mentions(before)
        after_dims = _find_dimension_mentions(after)
        if before_dims:
            group_dim = before_dims[0]
        if after_dims:
            metric_dim = after_dims[0]
    
    # Fallback: if BY-pattern didn't work, take first + second dimension
    if group_dim is None and all_dims:
        group_dim = all_dims[0]

    if metric_dim is None and len(all_dims) > 1:
        for dim in all_dims:
            if dim != group_dim:
                metric_dim = dim
                break
    
    # If group_dim is category and metric_dim is also category-like, fix it
    if group_dim == "category" and metric_dim == "subcategory":
        group_dim, metric_dim = "subcategory", "category"

    return group_dim, metric_dim


def _generic_ranked_analytics_answer(question_text: str, df: pd.DataFrame, top_n: int) -> tuple[str | None, list[dict]]:
    asks_rank = bool(re.search(r"\b(top|most|least|fewest|highest|lowest|max|min)\b", question_text))
    if not asks_rank:
        return None, []

    group_dim, metric_dim = _resolve_rank_dimensions(question_text)
    if not group_dim:
        return None, []

    group_col = _DIMENSION_COLUMNS.get(group_dim)
    if not group_col or group_col not in df.columns:
        return None, []

    asks_ascending = bool(re.search(r"\b(least|fewest|lowest|min)\b", question_text))

    if metric_dim and metric_dim != "project":
        metric_col = _DIMENSION_COLUMNS.get(metric_dim)
        if metric_col and metric_col in df.columns:
            series = _nunique_by(df, group_col, metric_col)
            if asks_ascending:
                series = series.sort_values(ascending=True)
            direction = "Least" if asks_ascending else "Top"
            heading = f"{direction} {_DIMENSION_LABELS[group_dim]} by unique {_DIMENSION_LABELS[metric_dim]}:"
            return _format_ranked_lines(heading, series, top_n=top_n), df.head(100).to_dict(orient="records")

    series = _series_counts(df, group_col)
    if asks_ascending:
        series = series.sort_values(ascending=True)
    direction = "Least" if asks_ascending else "Top"
    heading = f"{direction} {_DIMENSION_LABELS[group_dim]} by projects:"
    return _format_ranked_lines(heading, series, top_n=top_n), df.head(100).to_dict(orient="records")


def _format_ranked_lines(title: str, series: pd.Series, top_n: int = 10) -> str:
    if series is None or series.empty:
        return "No data found for that query."
    lines = [title]
    for idx, (label, value) in enumerate(series.head(top_n).items(), start=1):
        lines.append(f"{idx}. {label}: {int(value)}")
    return "\n".join(lines)


def _format_count_list(label: str, items: list[str], scope_suffix: str = "") -> str:
    count = len(items)
    noun = label if count == 1 else f"{label}s"
    lines = [f"I found {count} {noun}{scope_suffix}."]
    if items:
        lines.append(f"{label.title()}s:")
        lines.extend([f"- {item}" for item in items])
    return "\n".join(lines)


def _scope_suffix(route: dict) -> str:
    parts = []
    for key, label in [
        ("brand_hint", "brand"),
        ("client_hint", "client"),
        ("market_hint", "market"),
        ("category_hint", "category"),
        ("subcategory_hint", "subcategory"),
        ("dependent_var_hint", "dependent variable"),
    ]:
        value = _safe_str(route.get(key))
        if value:
            parts.append(f"{label} '{value}'")
    if not parts:
        return ""
    return " for " + ", ".join(parts)


def _deterministic_analytics_answer(question: str, route: dict) -> tuple[str | None, list[dict]]:
    q = _safe_str(question).lower()
    df = _apply_route_filters_to_df(complete_df, route or {})
    factors = _apply_route_filters_to_df(factors_df, route or {}) if not factors_df.empty else factors_df.copy()
    n = _extract_top_n(question, default=10)

    if df.empty and any(_safe_str((route or {}).get(k)) for k in ["brand_hint", "client_hint", "market_hint", "category_hint", "subcategory_hint", "dependent_var_hint"]):
        return "No data found for that query.", []

    generic_answer, generic_projects = _generic_ranked_analytics_answer(q, df, n)
    if generic_answer:
        return generic_answer, generic_projects

    # Basic counts
    if "how many projects" in q and "per" not in q and "within" not in q and "top" not in q and "least" not in q:
        return f"Total projects: {len(df)}", df.head(100).to_dict(orient="records")
    if "how many categories" in q and "per" not in q:
        values = sorted(df["Category"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()) if "Category" in df.columns else []
        return _format_count_list("category", values, _scope_suffix(route or {})), df.head(100).to_dict(orient="records")
    if "how many unique clients" in q:
        values = sorted(df["Client"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()) if "Client" in df.columns else []
        return _format_count_list("client", values, _scope_suffix(route or {})), df.head(100).to_dict(orient="records")
    if "how many markets" in q and "per" not in q and "within" not in q:
        values = sorted(df["MarketforBrand"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()) if "MarketforBrand" in df.columns else []
        return _format_count_list("market", values, _scope_suffix(route or {})), df.head(100).to_dict(orient="records")

    # Grouped and distinct counts
    if "records" in q and "per category" in q:
        return _format_ranked_lines("Records per category:", _series_counts(df, "Category"), top_n=9999), df.head(100).to_dict(orient="records")
    if ("top" in q and "categor" in q and "brand" in q) or ("number of brands per category" in q):
        return _format_ranked_lines(
            "Top categories by unique brands:",
            _nunique_by(df, "Category", "BrandModelled"),
            top_n=n,
        ), df.head(100).to_dict(orient="records")
    if ("brands per client" in q) or ("count of brands per client" in q):
        return _format_ranked_lines("Unique brands per client:", _nunique_by(df, "Client", "BrandModelled"), top_n=9999), df.head(100).to_dict(orient="records")
    if ("subcategories within each category" in q) or ("subcategories per category" in q):
        return _format_ranked_lines("Unique subcategories per category:", _nunique_by(df, "Category", "SubCategory"), top_n=9999), df.head(100).to_dict(orient="records")
    if "unique brands per category" in q:
        return _format_ranked_lines("Unique brands per category:", _nunique_by(df, "Category", "BrandModelled"), top_n=9999), df.head(100).to_dict(orient="records")
    if "unique markets per client" in q:
        return _format_ranked_lines("Unique markets per client:", _nunique_by(df, "Client", "MarketforBrand"), top_n=9999), df.head(100).to_dict(orient="records")

    # Top / least globals
    if "category has the most" in q or "most records" in q and "category" in q:
        s = _series_counts(df, "Category")
        if s.empty:
            return "No data found for that query.", []
        return f"Category with most records: {s.index[0]} ({int(s.iloc[0])})", df.head(100).to_dict(orient="records")
    if "client appears the most" in q or "top" in q and "client" in q and "project" in q:
        s = _series_counts(df, "Client")
        return _format_ranked_lines("Top clients by projects:", s, top_n=n), df.head(100).to_dict(orient="records")
    if "market has the highest" in q or "top" in q and "market" in q and "project" in q:
        s = _series_counts(df, "MarketforBrand")
        return _format_ranked_lines("Top markets by projects:", s, top_n=n), df.head(100).to_dict(orient="records")
    if "brand is modeled the most" in q or "top" in q and "brand" in q and "project" in q:
        s = _series_counts(df, "BrandModelled")
        return _format_ranked_lines("Top brands by projects:", s, top_n=n), df.head(100).to_dict(orient="records")
    if "least" in q and "category" in q and "record" in q:
        s = _series_counts(df, "Category").sort_values(ascending=True)
        return _format_ranked_lines("Least represented categories:", s, top_n=n), df.head(100).to_dict(orient="records")
    if "least" in q and "client" in q:
        s = _series_counts(df, "Client").sort_values(ascending=True)
        return _format_ranked_lines("Least frequent clients:", s, top_n=n), df.head(100).to_dict(orient="records")
    if "least" in q and "market" in q:
        s = _series_counts(df, "MarketforBrand").sort_values(ascending=True)
        return _format_ranked_lines("Least represented markets:", s, top_n=n), df.head(100).to_dict(orient="records")

    # Multi-level top/least
    if "top client within each category" in q:
        if not {"Category", "Client"}.issubset(df.columns):
            return "No data found for that query.", []
        grouped = df.groupby(["Category", "Client"]).size().reset_index(name="count")
        top_rows = grouped.sort_values(["Category", "count"], ascending=[True, False]).drop_duplicates(["Category"])
        lines = ["Top client within each category:"]
        for _, row in top_rows.iterrows():
            lines.append(f"- {row['Category']}: {row['Client']} ({int(row['count'])})")
        return "\n".join(lines), df.head(100).to_dict(orient="records")
    if "top market within each category" in q:
        if not {"Category", "MarketforBrand"}.issubset(df.columns):
            return "No data found for that query.", []
        grouped = df.groupby(["Category", "MarketforBrand"]).size().reset_index(name="count")
        top_rows = grouped.sort_values(["Category", "count"], ascending=[True, False]).drop_duplicates(["Category"])
        lines = ["Top market within each category:"]
        for _, row in top_rows.iterrows():
            lines.append(f"- {row['Category']}: {row['MarketforBrand']} ({int(row['count'])})")
        return "\n".join(lines), df.head(100).to_dict(orient="records")
    if "top subcategory" in q and "food" in q:
        if "Category" in df.columns:
            food_df = df[_contains_value(df["Category"].astype(str), "food")]
        else:
            food_df = df
        s = _series_counts(food_df, "SubCategory")
        if s.empty:
            return "No data found for that query.", []
        return f"Top subcategory in Food category: {s.index[0]} ({int(s.iloc[0])})", df.head(100).to_dict(orient="records")

    # Factor analytics
    if "factortype" in q and "most" in q:
        s = _series_counts(factors, "FactorType")
        return _format_ranked_lines("FactorType frequency:", s, top_n=n), factors.head(100).to_dict(orient="records")
    if "factortype" in q and ("least" in q or "less" in q):
        s = _series_counts(factors, "FactorType").sort_values(ascending=True)
        return _format_ranked_lines("Least used FactorType:", s, top_n=n), factors.head(100).to_dict(orient="records")
    if "factorname" in q and "most" in q:
        s = _series_counts(factors, "FactorName")
        return _format_ranked_lines("Most common FactorNames:", s, top_n=n), factors.head(100).to_dict(orient="records")
    if "factorname" in q and ("least" in q or "less" in q):
        s = _series_counts(factors, "FactorName").sort_values(ascending=True)
        return _format_ranked_lines("Less common FactorNames:", s, top_n=n), factors.head(100).to_dict(orient="records")
    if "emotional" in q and "factor" in q and "top" in q:
        emo = factors.copy()
        if "FactorType" in emo.columns:
            emo = emo[emo["FactorType"].astype(str).str.lower().str.contains("emotional", na=False)]
        s = _series_counts(emo, "FactorName")
        return _format_ranked_lines("Top emotional factors:", s, top_n=n), emo.head(100).to_dict(orient="records")

    # Comparative and advanced
    if "top vs least categories" in q or ("compare" in q and "category" in q and "count" in q):
        s = _series_counts(df, "Category")
        if s.empty:
            return "No data found for that query.", []
        high = (s.index[0], int(s.iloc[0]))
        low = (s.index[-1], int(s.iloc[-1]))
        return f"Top category: {high[0]} ({high[1]})\nLeast category: {low[0]} ({low[1]})", df.head(100).to_dict(orient="records")
    if "highest vs lowest brand count" in q and "market" in q:
        s = _nunique_by(df, "MarketforBrand", "BrandModelled")
        if s.empty:
            return "No data found for that query.", []
        return f"Highest brand count market: {s.index[0]} ({int(s.iloc[0])})\nLowest brand count market: {s.index[-1]} ({int(s.iloc[-1])})", df.head(100).to_dict(orient="records")
    if "max and min presence" in q and "client" in q and "categor" in q:
        s = _nunique_by(df, "Client", "Category")
        if s.empty:
            return "No data found for that query.", []
        return f"Max category presence client: {s.index[0]} ({int(s.iloc[0])})\nMin category presence client: {s.index[-1]} ({int(s.iloc[-1])})", df.head(100).to_dict(orient="records")
    if "only 1 client" in q and "categor" in q:
        s = _nunique_by(df, "Category", "Client")
        one_client = [idx for idx, val in s.items() if int(val) == 1]
        return _format_count_list("category", one_client), df.head(100).to_dict(orient="records")
    if "highest concentration in one market" in q and "categor" in q:
        if not {"Category", "MarketforBrand"}.issubset(df.columns):
            return "No data found for that query.", []
        grouped = df.groupby(["Category", "MarketforBrand"]).size().reset_index(name="count")
        total_by_cat = grouped.groupby("Category")["count"].sum()
        max_by_cat = grouped.groupby("Category")["count"].max()
        concentration = (max_by_cat / total_by_cat).sort_values(ascending=False)
        if concentration.empty:
            return "No data found for that query.", []
        top_category = concentration.index[0]
        return f"Category with highest one-market concentration: {top_category} ({round(float(concentration.iloc[0]) * 100, 1)}%)", df.head(100).to_dict(orient="records")
    if "client operates in maximum number of markets" in q:
        s = _nunique_by(df, "Client", "MarketforBrand")
        if s.empty:
            return "No data found for that query.", []
        return f"Client with maximum market coverage: {s.index[0]} ({int(s.iloc[0])} markets)", df.head(100).to_dict(orient="records")
    if "brands are most diversified across markets" in q:
        s = _nunique_by(df, "BrandModelled", "MarketforBrand")
        return _format_ranked_lines("Most diversified brands by market coverage:", s, top_n=n), df.head(100).to_dict(orient="records")
    if "most uneven distribution" in q and "categor" in q:
        if not {"Category", "MarketforBrand"}.issubset(df.columns):
            return "No data found for that query.", []
        grouped = df.groupby(["Category", "MarketforBrand"]).size().reset_index(name="count")
        gap_by_cat = grouped.groupby("Category")["count"].agg(lambda s: int(s.max() - s.min())).sort_values(ascending=False)
        if gap_by_cat.empty:
            return "No data found for that query.", []
        return f"Category with most uneven market distribution: {gap_by_cat.index[0]} (gap {int(gap_by_cat.iloc[0])})", df.head(100).to_dict(orient="records")

    return None, []


# API Endpoints
@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "api_key_present": bool(API_KEY)}


@app.post("/api/route-query")
async def api_route_query(request: RouteRequest):
    """Route a query to determine intent and required filters."""
    history = request.history or []
    route_history = request.route_history or []
    raw_route = route_query(request.question, history)
    merged_route = merge_followup_route(raw_route, route_history)
    merged_route = _normalize_route_with_question(request.question, merged_route)

    response = merged_route.copy()
    response["raw_route"] = raw_route
    response["merged_route"] = merged_route
    return response


@app.post("/api/filter-projects")
async def api_filter_projects(route: FilterProjectsRequest):
    """Filter projects based on route hints."""
    candidates, clarify_msg = filter_projects(route.model_dump())
    return {
        "projects": candidates.to_dict(orient="records"),
        "clarification_message": clarify_msg,
        "row_count": len(candidates),
    }


@app.post("/api/filter-factors")
async def api_filter_factors(route: FilterProjectsRequest):
    """Filter factors-db directly and return matching factor rows plus unique projects."""
    factors, unique_projects = filter_factors_directly(route.model_dump())

    if factors.empty:
        return {
            "projects": [],
            "factors": [],
            "clarification_message": None,
            "row_count": 0,
        }

    needs_clarification = len(unique_projects) > 1 and not str(route.coe_job_number_hint or "").strip()
    clarification_message = None
    if needs_clarification:
        project_options = factor_project_options(factors)
        clarification_message = (
            "I found multiple projects with factors matching your criteria. "
            "Please provide more detail (CoE job number, brand, or market).\n\n"
            f"Projects:\n{project_options}"
        )

    return {
        "projects": unique_projects.to_dict(orient="records"),
        "factors": factors.to_dict(orient="records"),
        "clarification_message": clarification_message,
        "row_count": len(factors),
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
    
    route_for_answer = (request.route or {}).copy()

    # Context-only fix: when users ask for dependent variable, ensure
    # Dependentvar is included in the LLM context even though it is not a filter.
    asks_for_dependent_variable = bool(
        re.search(r"\b(what|which)\b.*\bdependent\s*(variable|var|dv)\b", _safe_str(request.question).lower())
    )
    if asks_for_dependent_variable and not _safe_str(route_for_answer.get("dependent_var_hint")):
        route_for_answer["dependent_var_hint"] = "__requested_output_field__"

    answer = answer_with_groq(request.question, route_for_answer, project_df, factor_df)

    # Match Streamlit behavior: prompt for factors when exactly one unique project is found.
    if not project_df.empty and all(col in project_df.columns for col in ["BrandModelled", "MarketforBrand"]):
        unique_projects_count = len(project_df[["BrandModelled", "MarketforBrand"]].drop_duplicates())
        if unique_projects_count == 1:
            first_project = project_df.iloc[0]
            brand = _safe_str(first_project.get("BrandModelled", ""))
            market = _safe_str(first_project.get("MarketforBrand", ""))
            if brand and market and _check_project_has_factors(brand, market):
                answer += "\n\nWould you like to know what factors influenced this project?"

    return {"answer": answer}


@app.post("/api/analytics-answer")
async def api_analytics_answer(request: AnalyticsAnswerRequest):
    """Handle analytics intent with pre-computed stats, like Streamlit path."""
    if not client:
        return {"answer": "GROQ_API_KEY is missing.", "projects": []}

    route = request.route or {}
    analytics_type = route.get("analytics_type")
    analytics_limit = route.get("analytics_limit", 10)

    deterministic_answer, deterministic_projects = _deterministic_analytics_answer(request.question, route)
    if deterministic_answer:
        return {
            "answer": deterministic_answer,
            "projects": deterministic_projects,
            "analytics_type": analytics_type,
            "analytics_limit": analytics_limit,
        }

    if not analytics_type:
        return {
            "answer": "I could not determine what analytics you're looking for.",
            "projects": [],
            "analytics_type": None,
            "analytics_limit": analytics_limit,
        }

    stats = compute_aggregation_stats(complete_df.copy(), analytics_type, analytics_limit)
    if not stats:
        return {
            "answer": "No data found for that query.",
            "projects": [],
            "analytics_type": analytics_type,
            "analytics_limit": analytics_limit,
        }

    answer = answer_with_groq(
        request.question,
        route,
        complete_df.iloc[0:0].copy(),
        factors_df.iloc[0:0].copy(),
        stats,
    )

    # Keep payload small for the React app while still exposing a retrieval sample.
    project_sample = complete_df.head(100).to_dict(orient="records")
    return {
        "answer": answer,
        "projects": project_sample,
        "analytics_type": analytics_type,
        "analytics_limit": analytics_limit,
    }


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
            "market_options": sorted(_series_for_counts(complete_df, market_col).dropna().unique().tolist()) if market_col else [],
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
    market_options = sorted(_series_for_counts(complete_df, market_col).dropna().unique().tolist())

    selected_market = market if market in market_options else (market_options[0] if market_options else None)
    if not selected_market:
        return {"selected_market": None, "categories_subcategories": [], "brands": []}

    market_df = complete_df[_contains_ci_with_col(complete_df[market_col], selected_market, market_col)]

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
