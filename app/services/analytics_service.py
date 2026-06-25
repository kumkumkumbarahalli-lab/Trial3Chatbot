from __future__ import annotations

import re

import pandas as pd

from app.core.text_utils import MARKET_VALUE_COLUMNS, normalize_market_values, normalize_text, safe_str


def _contains_value(series: pd.Series, hint: str) -> pd.Series:
    needle = normalize_text(hint)
    if not needle:
        return pd.Series(False, index=series.index)
    return series.astype(str).apply(lambda x: needle in normalize_text(x))


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
        hint = safe_str(route.get(route_key))
        if hint and col in filtered.columns:
            mask &= _contains_value(filtered[col].astype(str), hint)

    return filtered[mask].copy()


def _extract_top_n(question: str, default: int = 10) -> int:
    match = re.search(r"\b(?:top|least)\s+(\d+)\b", safe_str(question).lower())
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
    if col in MARKET_VALUE_COLUMNS:
        series = series.apply(normalize_market_values).explode().dropna()
        series = series.astype(str).str.strip()
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
    if value_col in MARKET_VALUE_COLUMNS:
        working[value_col] = working[value_col].apply(normalize_market_values)
        working = working.explode(value_col)
        working[value_col] = working[value_col].astype(str).str.strip()
        working = working[working[value_col] != ""]
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


def _format_top_dimension_line(df: pd.DataFrame, col: str, label: str, max_items: int = 5) -> str | None:
    counts = _series_counts(df, col)
    if counts.empty:
        return None
    parts = []
    for value, count in counts.head(max_items).items():
        parts.append(f"{value} ({int(count)})")
    return f"Top {label}: " + ", ".join(parts)


def _project_total_with_details(df: pd.DataFrame, route: dict) -> str:
    scope = _scope_suffix(route or {})
    lines = [f"Total projects{scope}: {len(df)}"]

    if df.empty:
        return "\n".join(lines)

    route_to_col = {
        "brand_hint": "BrandModelled",
        "client_hint": "Client",
        "market_hint": "MarketforBrand",
        "category_hint": "Category",
        "subcategory_hint": "SubCategory",
        "dependent_var_hint": "Dependentvar",
    }
    filtered_cols = {
        col
        for route_key, col in route_to_col.items()
        if safe_str((route or {}).get(route_key))
    }

    detail_candidates = [
        ("BrandModelled", "brands"),
        ("MarketforBrand", "markets"),
        ("SubCategory", "subcategories"),
        ("Category", "categories"),
    ]

    detail_lines = []
    for col, label in detail_candidates:
        if col in filtered_cols or col not in df.columns:
            continue
        line = _format_top_dimension_line(df, col, label)
        if line:
            detail_lines.append(line)
        if len(detail_lines) >= 3:
            break

    if detail_lines:
        lines.extend(detail_lines)

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
        value = safe_str(route.get(key))
        if value:
            parts.append(f"{label} '{value}'")
    if not parts:
        return ""
    return " for " + ", ".join(parts)


def deterministic_analytics_answer(question: str, route: dict, complete_df: pd.DataFrame, factors_df: pd.DataFrame) -> tuple[str | None, list[dict]]:
    q = safe_str(question).lower()
    df = _apply_route_filters_to_df(complete_df, route or {})
    factors = _apply_route_filters_to_df(factors_df, route or {}) if not factors_df.empty else factors_df.copy()
    n = _extract_top_n(question, default=10)

    if df.empty and any(safe_str((route or {}).get(k)) for k in ["brand_hint", "client_hint", "market_hint", "category_hint", "subcategory_hint", "dependent_var_hint"]):
        return "No data found for that query.", []

    generic_answer, generic_projects = _generic_ranked_analytics_answer(q, df, n)
    if generic_answer:
        return generic_answer, generic_projects

    asks_project_total = bool(
        re.search(r"\b(how many|number of|count(?: of)?|total)\b.*\bprojects?\b", q)
    )
    if asks_project_total and all(token not in q for token in [" per ", "within", "top", "least", "most", "each"]):
        return _project_total_with_details(df, route or {}), df.head(100).to_dict(orient="records")
    if "how many categories" in q and "per" not in q:
        values = sorted(df["Category"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()) if "Category" in df.columns else []
        return _format_count_list("category", values, _scope_suffix(route or {})), df.head(100).to_dict(orient="records")
    if "how many unique clients" in q:
        values = sorted(df["Client"].astype(str).str.strip().replace("", pd.NA).dropna().unique().tolist()) if "Client" in df.columns else []
        return _format_count_list("client", values, _scope_suffix(route or {})), df.head(100).to_dict(orient="records")
    if "how many markets" in q and "per" not in q and "within" not in q:
        values = sorted(_series_counts(df, "MarketforBrand").index.tolist()) if "MarketforBrand" in df.columns else []
        return _format_count_list("market", values, _scope_suffix(route or {})), df.head(100).to_dict(orient="records")

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