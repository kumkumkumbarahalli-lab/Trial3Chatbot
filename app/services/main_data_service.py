from __future__ import annotations

import json

import pandas as pd

from app.core.text_utils import cell_matches_hint, normalize_text, split_multi_values


def safe_str(value):
    return "" if value is None else str(value).strip()


def build_catalog_text(complete_df: pd.DataFrame) -> str:
    cols = [
        c
        for c in [
            "CoEJobnumber",
            "BrandModelled",
            "MarketforBrand",
            "Dependentvar",
            "Category",
            "SubCategory",
            "Client",
        ]
        if c in complete_df.columns
    ]
    sample = complete_df[cols].head(20).to_dict(orient="records")
    return json.dumps(sample, ensure_ascii=False, indent=2)


def norm_text(value):
    return normalize_text(value)


def split_cell_values(value):
    return split_multi_values(value)


def value_matches(cell_value, hint):
    return cell_matches_hint(cell_value, hint, is_multi_value=True)


def contains_mask(df: pd.DataFrame, col: str, hint):
    if col not in df.columns or not safe_str(hint):
        return pd.Series(False, index=df.index)
    return df[col].astype(str).apply(lambda x: value_matches(x, hint))


def values_are_similar(values_a, values_b):
    norm_a = [norm_text(v) for v in values_a if norm_text(v)]
    norm_b = [norm_text(v) for v in values_b if norm_text(v)]
    if not norm_a or not norm_b:
        return False
    for a in norm_a:
        for b in norm_b:
            if a == b or a in b or b in a:
                return True
    return False


def _project_display_columns(df):
    relevant_cols = {
        "CoEJobnumber",
        "BrandModelled",
        "MarketforBrand",
        "Client",
        "Category",
        "SubCategory",
    }
    return [col for col in df.columns if col in relevant_cols]


def _project_display_label(column_name):
    label_map = {
        "CoEJobnumber": "CoE Job Number",
        "BrandModelled": "Brand",
        "MarketforBrand": "Market",
        "Client": "Client",
        "Category": "Category",
        "SubCategory": "Subcategory",
    }
    return label_map.get(column_name, column_name)


def unique_project_options(df: pd.DataFrame):
    cols = _project_display_columns(df)
    opts = df[cols].drop_duplicates().head(12)
    lines = []
    for idx, row in enumerate(opts.to_dict(orient="records"), start=1):
        line_bits = []
        for c in cols:
            if c in row and safe_str(row[c]):
                line_bits.append(f"{_project_display_label(c)}: {row[c]}")
        lines.append(f"{idx}. " + " | ".join(line_bits))
    return "\n".join(lines)


def factor_project_options(factor_rows: pd.DataFrame):
    if factor_rows.empty:
        return ""

    display_cols = _project_display_columns(factor_rows)
    if not display_cols:
        return ""

    project_rows = factor_rows[display_cols].drop_duplicates().head(12)
    lines = []
    for idx, proj_data in enumerate(project_rows.to_dict(orient="records"), start=1):
        line_bits = []
        for col in display_cols:
            value = safe_str(proj_data.get(col, ""))
            if value:
                line_bits.append(f"{_project_display_label(col)}: {value}")

        lines.append(f"{idx}. " + " | ".join(line_bits))

    return "\n".join(lines)


def filter_projects(complete_df: pd.DataFrame, route: dict):
    df = complete_df.copy()
    mask = pd.Series(True, index=df.index)
    used_filters = 0

    job_hint = route.get("coe_job_number_hint")
    if safe_str(job_hint) and "CoEJobnumber" in df.columns:
        mask &= contains_mask(df, "CoEJobnumber", job_hint)
        used_filters += 1

    market_hint = route.get("market_hint")
    if safe_str(market_hint) and "MarketforBrand" in df.columns:
        mask &= contains_mask(df, "MarketforBrand", market_hint)
        used_filters += 1

    dep_hint = route.get("dependent_var_hint")
    if safe_str(dep_hint) and "Dependentvar" in df.columns:
        mask &= contains_mask(df, "Dependentvar", dep_hint)
        used_filters += 1

    cat_hint = route.get("subcategory_hint") or route.get("category_hint")
    if safe_str(cat_hint):
        sub_mask = contains_mask(df, "SubCategory", cat_hint)
        cat_mask = contains_mask(df, "Category", cat_hint)
        scope = safe_str(route.get("category_scope", "")).lower()

        if scope == "subcategory":
            if sub_mask.any():
                mask &= sub_mask
            elif cat_mask.any():
                mask &= cat_mask
            else:
                mask &= pd.Series(False, index=df.index)
            used_filters += 1
        elif scope == "category":
            if cat_mask.any():
                mask &= cat_mask
            elif sub_mask.any():
                mask &= sub_mask
            else:
                mask &= pd.Series(False, index=df.index)
            used_filters += 1
        else:
            if sub_mask.any() and cat_mask.any():
                sub_vals = df.loc[sub_mask, "SubCategory"].astype(str).unique().tolist() if "SubCategory" in df.columns else []
                cat_vals = df.loc[cat_mask, "Category"].astype(str).unique().tolist() if "Category" in df.columns else []
                if values_are_similar(sub_vals, cat_vals):
                    return df.iloc[0:0], "Found matches in both Category and SubCategory. Which level would help?"
            if sub_mask.any():
                mask &= sub_mask
                used_filters += 1
            elif cat_mask.any():
                mask &= cat_mask
                used_filters += 1

    brand_hint = route.get("brand_hint")
    client_hint = route.get("client_hint")
    party_hint = brand_hint or client_hint
    if safe_str(party_hint):
        brand_mask = contains_mask(df, "BrandModelled", party_hint)
        client_mask = contains_mask(df, "Client", party_hint)
        scope = safe_str(route.get("brand_client_scope", "")).lower()

        if scope == "brand":
            if brand_mask.any():
                mask &= brand_mask
            elif client_mask.any():
                mask &= client_mask
            else:
                mask &= pd.Series(False, index=df.index)
            used_filters += 1
        elif scope == "client":
            if client_mask.any():
                mask &= client_mask
            elif brand_mask.any():
                mask &= brand_mask
            else:
                mask &= pd.Series(False, index=df.index)
            used_filters += 1
        else:
            if brand_mask.any():
                mask &= brand_mask
                used_filters += 1
            elif client_mask.any():
                mask &= client_mask
                used_filters += 1

    if used_filters == 0:
        return df.iloc[0:0], "To find what you're looking for, mention at least one: Brand, Market, Category, or Client."

    return df[mask].copy(), None


def filter_factors_directly(factors_df: pd.DataFrame, route: dict):
    df = factors_df.copy()
    mask = pd.Series(True, index=df.index)
    used_filters = 0

    job_hint = route.get("coe_job_number_hint")
    if safe_str(job_hint) and "CoEJobnumber" in df.columns:
        mask &= contains_mask(df, "CoEJobnumber", job_hint)
        used_filters += 1

    market_hint = route.get("market_hint")
    if safe_str(market_hint) and "MarketforBrand" in df.columns:
        mask &= contains_mask(df, "MarketforBrand", market_hint)
        used_filters += 1

    brand_hint = route.get("brand_hint")
    client_hint = route.get("client_hint")
    party_hint = brand_hint or client_hint
    if safe_str(party_hint):
        brand_mask = contains_mask(df, "BrandModelled", party_hint)
        client_mask = contains_mask(df, "Client", party_hint) if "Client" in df.columns else pd.Series(False, index=df.index)

        if brand_mask.any():
            mask &= brand_mask
            used_filters += 1
        elif client_mask.any():
            mask &= client_mask
            used_filters += 1

    ft = safe_str(route.get("factor_type_hint", "")).lower()
    if ft and "FactorType" in df.columns:
        mask &= df["FactorType"].astype(str).str.lower().str.contains(ft, na=False)
        used_filters += 1

    if used_filters == 0:
        return df.iloc[0:0].copy(), None

    filtered_factors = df[mask].copy()
    unique_projects = filtered_factors[["CoEJobnumber", "BrandModelled", "MarketforBrand"]].drop_duplicates()
    return filtered_factors, unique_projects


def fetch_factors_for_projects(factors_df: pd.DataFrame, projects: pd.DataFrame, route: dict):
    if projects.empty:
        return factors_df.iloc[0:0].copy()

    rows = []
    for _, project_row in projects.iterrows():
        row_mask = pd.Series(True, index=factors_df.index)

        if "CoEJobnumber" in factors_df.columns and safe_str(project_row.get("CoEJobnumber", "")):
            row_mask &= factors_df["CoEJobnumber"].astype(str) == safe_str(project_row.get("CoEJobnumber", ""))
        if "BrandModelled" in factors_df.columns and safe_str(project_row.get("BrandModelled", "")):
            row_mask &= contains_mask(factors_df, "BrandModelled", safe_str(project_row.get("BrandModelled", "")))
        if "MarketforBrand" in factors_df.columns and safe_str(project_row.get("MarketforBrand", "")):
            row_mask &= contains_mask(factors_df, "MarketforBrand", safe_str(project_row.get("MarketforBrand", "")))

        rows.append(factors_df[row_mask])

    if not rows:
        return factors_df.iloc[0:0].copy()

    out = pd.concat(rows, ignore_index=True).drop_duplicates()

    ft = safe_str(route.get("factor_type_hint", "")).lower()
    if ft and "FactorType" in out.columns:
        out = out[out["FactorType"].astype(str).str.lower().str.contains(ft, na=False)]

    if "sequence" in out.columns:
        out = out.sort_values("sequence")

    return out


def project_summary(row):
    bits = []
    for col in ["CoEJobnumber", "BrandModelled", "MarketforBrand", "Dependentvar", "Category", "SubCategory", "Client"]:
        if col in row and safe_str(row[col]):
            bits.append(f"{col}: {row[col]}")
    return "\n".join(bits)


def factor_summary(fdf: pd.DataFrame):
    if fdf.empty:
        return "No linked factor rows found."
    cols = [c for c in ["sequence", "FactorType", "FactorName", "FactorValue", "FactorLabel"] if c in fdf.columns]
    return fdf[cols].to_string(index=False)


def factor_type_rank(ftype):
    t = safe_str(ftype).lower()
    if t in ["dv", "dependent variable", "dependentvar"]:
        return 0
    if t in ["kpi", "kpis"]:
        return 1
    return 2


def format_factors_response(fdf: pd.DataFrame):
    if fdf.empty:
        return "No linked factor rows found for this selection."

    if "FactorType" not in fdf.columns or "FactorName" not in fdf.columns:
        return factor_summary(fdf)

    ordered = fdf.copy()
    if "sequence" in ordered.columns:
        ordered = ordered.sort_values("sequence")

    first_seen = {}
    for i, ft in enumerate(ordered["FactorType"].astype(str).tolist()):
        if ft not in first_seen:
            first_seen[ft] = i

    factor_types = list(first_seen.keys())
    factor_types.sort(key=lambda ft: (factor_type_rank(ft), first_seen.get(ft, 99999)))

    lines = []
    for factor_type in factor_types:
        group = ordered[ordered["FactorType"].astype(str) == factor_type]
        names = [safe_str(n) for n in group["FactorName"].tolist() if safe_str(n)]
        unique_names = list(dict.fromkeys(names))
        if not unique_names:
            continue
        lines.append(f"{factor_type}")
        for name in unique_names:
            lines.append(f"- {name}")
        lines.append("")

    return "\n".join(lines).strip() or "No linked factor rows found for this selection."


def build_context_for_groq(project_rows: pd.DataFrame, route: dict, question=None):
    if project_rows.empty:
        return []

    core_fields = ["BrandModelled", "MarketforBrand", "Category"]
    optional_fields = []

    question_text = safe_str(question).lower()

    if safe_str(route.get("subcategory_hint")) or safe_str(route.get("category_scope")).lower() == "subcategory" or "subcategor" in question_text:
        optional_fields.append("SubCategory")
    if safe_str(route.get("client_hint")) or "client" in question_text:
        optional_fields.append("Client")
    if safe_str(route.get("dependent_var_hint")):
        optional_fields.append("Dependentvar")

    fields_to_include = core_fields + optional_fields
    fields_to_include = [f for f in fields_to_include if f in project_rows.columns]
    records = project_rows[fields_to_include].drop_duplicates().to_dict(orient="records")
    return records


def _is_count_style_question(question):
    q = safe_str(question).lower()
    count_markers = ["how many", "count", "number of", "total", "how much"]
    return any(marker in q for marker in count_markers)


def _detect_count_dimension(question):
    q = safe_str(question).lower()

    if "subcategor" in q or "sub categor" in q:
        return {"column": "SubCategory", "singular": "subcategory", "plural": "subcategories", "heading": "Subcategories"}
    if "categor" in q:
        return {"column": "Category", "singular": "category", "plural": "categories", "heading": "Categories"}
    if "market" in q or "country" in q:
        return {"column": "MarketforBrand", "singular": "market", "plural": "markets", "heading": "Markets"}
    if "client" in q:
        return {"column": "Client", "singular": "client", "plural": "clients", "heading": "Clients"}
    if "brand" in q:
        return {"column": "BrandModelled", "singular": "brand", "plural": "brands", "heading": "Brands"}
    if "dependent" in q or "dv" in q:
        return {
            "column": "Dependentvar",
            "singular": "dependent variable",
            "plural": "dependent variables",
            "heading": "Dependent Variables",
        }
    if "project" in q:
        return {"column": None, "singular": "project", "plural": "projects", "heading": "Projects"}

    return None


def _build_scope_suffix(route):
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


def build_deterministic_count_response(question, route, project_rows, analytics_stats=None):
    if analytics_stats:
        return None

    if project_rows is None or project_rows.empty:
        return None

    if safe_str(route.get("intent")).lower() != "project_lookup":
        return None

    if not _is_count_style_question(question):
        return None

    dim = _detect_count_dimension(question)
    if dim is None:
        return None

    scope_suffix = _build_scope_suffix(route)

    if dim["column"] is None:
        combo_cols = [c for c in ["BrandModelled", "MarketforBrand", "Category"] if c in project_rows.columns]
        if not combo_cols:
            return None
        unique_projects = project_rows[combo_cols].astype(str).applymap(str.strip)
        unique_projects = unique_projects[(unique_projects != "").any(axis=1)].drop_duplicates()
        values = []
        for row in unique_projects.to_dict(orient="records"):
            parts = [safe_str(row.get(col)) for col in combo_cols if safe_str(row.get(col))]
            if parts:
                values.append(" | ".join(parts))
    else:
        col = dim["column"]
        if col not in project_rows.columns:
            return None
        series = project_rows[col].astype(str).str.strip()
        series = series[series != ""]
        values = list(dict.fromkeys(series.tolist()))

    count = len(values)
    noun = dim["singular"] if count == 1 else dim["plural"]

    lines = [f"I found {count} {noun}{scope_suffix}."]
    if values:
        lines.append(f"{dim['heading']}:")
        lines.extend([f"- {value}" for value in values])

    return "\n".join(lines)


def check_project_has_factors(factors_df: pd.DataFrame, brand, market):
    if factors_df.empty:
        return False

    mask = pd.Series(True, index=factors_df.index)

    if "BrandModelled" in factors_df.columns and safe_str(brand):
        mask &= factors_df["BrandModelled"].astype(str).str.lower() == safe_str(brand).lower()

    if "MarketforBrand" in factors_df.columns and safe_str(market):
        mask &= factors_df["MarketforBrand"].astype(str).str.lower() == safe_str(market).lower()

    return mask.any()


def _is_missing_route_value(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def merge_followup_route(route, route_history):
    if safe_str(route.get("intent")).lower() != "follow_up":
        return route

    if not route_history:
        return route

    base_route = None
    for previous_route in reversed(route_history):
        prev_intent = safe_str(previous_route.get("intent")).lower()
        if prev_intent not in ["follow_up", "clarify"]:
            base_route = previous_route
            break

    if base_route is None:
        return route

    merged = route.copy()
    inherit_keys = [
        "brand_hint",
        "client_hint",
        "market_hint",
        "category_hint",
        "subcategory_hint",
        "dependent_var_hint",
        "factor_type_hint",
        "coe_job_number_hint",
        "brand_client_scope",
        "category_scope",
        "analytics_type",
        "analytics_limit",
    ]

    for key in inherit_keys:
        if _is_missing_route_value(merged.get(key)) and not _is_missing_route_value(base_route.get(key)):
            merged[key] = base_route.get(key)

    base_intent = safe_str(base_route.get("intent")).lower()
    if safe_str(merged.get("intent")).lower() == "follow_up":
        if safe_str(base_route.get("factor_type_hint")) or base_intent == "factor_lookup":
            merged["intent"] = "factor_lookup"
        elif base_intent == "analytics" and not _is_missing_route_value(base_route.get("analytics_type")):
            merged["intent"] = "analytics"
        else:
            merged["intent"] = "project_lookup"

    return merged


def compute_aggregation_stats(df: pd.DataFrame, analytics_type, limit=10):
    stats = {}

    if not df.empty:
        analytics_type_value = safe_str(analytics_type).lower()
        is_top_request = "top" in analytics_type_value or "most" in analytics_type_value
        is_least_request = "least" in analytics_type_value
        refers_brand = "brand" in analytics_type_value
        refers_category = "category" in analytics_type_value or "categories" in analytics_type_value
        refers_market = any(token in analytics_type_value for token in ["market", "markets", "country", "countries"])
        refers_client = "client" in analytics_type_value or "clients" in analytics_type_value
        refers_dependent = any(token in analytics_type_value for token in ["dependent", "dependents", "dependentvar", "dv"])

        if is_top_request:
            if refers_brand:
                stats["top_brands"] = df["BrandModelled"].value_counts().head(limit).to_dict() if "BrandModelled" in df.columns else {}
            elif refers_category:
                stats["top_categories"] = df["Category"].value_counts().head(limit).to_dict() if "Category" in df.columns else {}
                if "Category" in df.columns and "BrandModelled" in df.columns:
                    grouped = (
                        df[["Category", "BrandModelled"]]
                        .astype(str)
                        .apply(lambda c: c.str.strip())
                        .replace("", pd.NA)
                        .dropna()
                        .drop_duplicates()
                        .groupby("Category")["BrandModelled"]
                        .nunique()
                        .sort_values(ascending=False)
                        .head(limit)
                    )
                    stats["top_categories_by_brands"] = grouped.to_dict()
            elif refers_market:
                stats["top_markets"] = df["MarketforBrand"].value_counts().head(limit).to_dict() if "MarketforBrand" in df.columns else {}
            elif refers_client:
                stats["top_clients"] = df["Client"].value_counts().head(limit).to_dict() if "Client" in df.columns else {}
            elif refers_dependent:
                stats["top_dependent_vars"] = df["Dependentvar"].value_counts().head(limit).to_dict() if "Dependentvar" in df.columns else {}

        elif is_least_request:
            if refers_brand:
                stats["least_brands"] = df["BrandModelled"].value_counts().tail(limit).to_dict() if "BrandModelled" in df.columns else {}
            elif refers_category:
                stats["least_categories"] = df["Category"].value_counts().tail(limit).to_dict() if "Category" in df.columns else {}
            elif refers_market:
                stats["least_markets"] = df["MarketforBrand"].value_counts().tail(limit).to_dict() if "MarketforBrand" in df.columns else {}
            elif refers_client:
                stats["least_clients"] = df["Client"].value_counts().tail(limit).to_dict() if "Client" in df.columns else {}
            elif refers_dependent:
                stats["least_dependent_vars"] = df["Dependentvar"].value_counts().tail(limit).to_dict() if "Dependentvar" in df.columns else {}

    return stats
