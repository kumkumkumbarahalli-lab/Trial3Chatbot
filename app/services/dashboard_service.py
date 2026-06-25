from __future__ import annotations

import pandas as pd

from app.core.text_utils import (
    MARKET_VALUE_COLUMNS,
    MULTI_VALUE_COLUMNS,
    cell_matches_hint,
    market_matches_hint,
    series_for_counts,
    split_multi_values,
)


def pick_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def contains_with_column(series: pd.Series, value: str, column_name: str | None) -> pd.Series:
    if not value:
        return pd.Series(False, index=series.index)
    if column_name in MARKET_VALUE_COLUMNS:
        return series.astype(str).apply(lambda cell: market_matches_hint(cell, value))
    is_multi = bool(column_name and column_name in MULTI_VALUE_COLUMNS)
    return series.astype(str).apply(lambda cell: cell_matches_hint(cell, value, is_multi))


def unique_count(df: pd.DataFrame, column: str | None) -> int:
    series = series_for_counts(df, column)
    if series.empty:
        return 0
    return int(series.nunique())


def value_counts(df: pd.DataFrame, column: str | None, top_n: int = 10) -> list[dict]:
    series = series_for_counts(df, column)
    if series.empty:
        return []
    counts = series.value_counts().head(top_n)
    return [{"label": str(label), "count": int(count)} for label, count in counts.items()]


def top_categories_by_brand_count(df: pd.DataFrame, category_col: str | None, brand_col: str | None, top_n: int = 10) -> list[dict]:
    if not category_col or not brand_col:
        return []

    working = df[[category_col, brand_col]].copy()
    working[category_col] = working[category_col].astype(str).str.strip()
    working[brand_col] = working[brand_col].astype(str).str.strip()
    working = working[(working[category_col] != "") & (working[brand_col] != "")]

    if brand_col in MULTI_VALUE_COLUMNS:
        working[brand_col] = working[brand_col].apply(split_multi_values)
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


def brand_distribution_for_category(df: pd.DataFrame, category_col: str | None, brand_col: str | None, selected_category: str | None) -> tuple[str | None, list[str], list[dict]]:
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
    chosen_df = working[working[category_col] == chosen]

    if brand_col in MULTI_VALUE_COLUMNS:
        chosen_df = chosen_df.copy()
        chosen_df[brand_col] = chosen_df[brand_col].apply(split_multi_values)
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


def build_dashboard_summary(complete_df: pd.DataFrame, selected_category: str | None = None) -> dict:
    category_col = pick_column(complete_df, ["Category"])
    subcategory_col = pick_column(complete_df, ["SubCategory"])
    client_col = pick_column(complete_df, ["Client", "ClientName"])
    brand_col = pick_column(complete_df, ["BrandModelled"])
    market_col = pick_column(complete_df, ["MarketforBrand", "Market", "Country"])

    chosen_category, category_options, brand_distribution = brand_distribution_for_category(
        complete_df,
        category_col,
        brand_col,
        selected_category,
    )

    return {
        "kpis": {
            "total_records": int(len(complete_df)),
            "unique_categories": unique_count(complete_df, category_col),
            "unique_subcategories": unique_count(complete_df, subcategory_col),
            "unique_clients": unique_count(complete_df, client_col),
            "unique_brands": unique_count(complete_df, brand_col),
            "unique_markets": unique_count(complete_df, market_col),
        },
        "charts": {
            "brand_distribution_for_selected_category": brand_distribution,
            "top_categories_by_brand_count": top_categories_by_brand_count(complete_df, category_col, brand_col, top_n=9999),
            "top_markets": value_counts(complete_df, market_col, top_n=10),
            "all_markets": value_counts(complete_df, market_col, top_n=9999),
            "top_brands": value_counts(complete_df, brand_col, top_n=10),
        },
        "slicers": {
            "selected_category": chosen_category,
            "category_options": category_options,
            "market_options": sorted(series_for_counts(complete_df, market_col).dropna().unique().tolist()) if market_col else [],
        },
    }


def build_market_breakdown(complete_df: pd.DataFrame, market: str | None = None) -> dict:
    market_col = pick_column(complete_df, ["MarketforBrand", "Market", "Country"])
    category_col = pick_column(complete_df, ["Category"])
    subcategory_col = pick_column(complete_df, ["SubCategory"])
    brand_col = pick_column(complete_df, ["BrandModelled"])

    if not market_col:
        return {"selected_market": None, "categories_subcategories": [], "brands": []}

    market_options = sorted(series_for_counts(complete_df, market_col).dropna().unique().tolist())
    selected_market = market if market in market_options else (market_options[0] if market_options else None)
    if not selected_market:
        return {"selected_market": None, "categories_subcategories": [], "brands": []}

    market_df = complete_df[contains_with_column(complete_df[market_col], selected_market, market_col)]

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

    brands = value_counts(market_df, brand_col, top_n=9999)

    return {
        "selected_market": selected_market,
        "categories_subcategories": cat_subcat,
        "brands": brands,
    }