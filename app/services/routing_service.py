from __future__ import annotations

import re

from app.core.text_utils import safe_str


def _is_count_style_question(question: str) -> bool:
    q = safe_str(question).lower()
    return any(token in q for token in ["how many", "count", "number of", "total"])


def _is_affirmative_followup(question: str) -> bool:
    q = safe_str(question).lower().strip(" .!?")
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
        value = safe_str(match.group(1)).strip(" .,!?:;\"'")
        if value:
            return value
    return None


def normalize_route_with_question(question: str, route: dict) -> dict:
    normalized = (route or {}).copy()
    q = safe_str(question)
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

    if has_subcategory_word:
        normalized["category_scope"] = "subcategory"
    elif has_category_word:
        normalized["category_scope"] = "category"

    category_hint = safe_str(normalized.get("category_hint"))
    subcategory_hint = safe_str(normalized.get("subcategory_hint"))

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

    if has_subcategory_word and not safe_str(normalized.get("category_hint")):
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

    if not subcategory_hint and has_subcategory_word and safe_str(normalized.get("category_scope")) == "subcategory":
        extracted_subcategory = _extract_value_with_patterns(
            q,
            [
                r"\bsub\s*category\s*[:\-]?\s*([a-zA-Z0-9&/\-\s]+?)\b(?:$|[?.!,])",
                r"\bsubcategories\s+for\s+([a-zA-Z0-9&/\-\s]+?)\b",
            ],
        )
        if extracted_subcategory:
            normalized["subcategory_hint"] = extracted_subcategory

    analytics_type = safe_str(normalized.get("analytics_type")).lower()
    if analytics_type and any(token in analytics_type for token in ["top", "most", "least", "frequent"]):
        normalized["intent"] = "analytics"
    elif safe_str(normalized.get("intent")).lower() == "analytics":
        normalized["intent"] = "project_lookup"

    if looks_analytics and not is_affirmative and not asks_for_dependent_variable:
        normalized["intent"] = "analytics"

    if _is_count_style_question(q) and safe_str(normalized.get("intent")).lower() == "clarify":
        has_any_filter = any(
            safe_str(normalized.get(key))
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

    if asks_for_dependent_variable and safe_str(normalized.get("dependent_var_hint")):
        normalized["dependent_var_hint"] = None

    if is_affirmative and safe_str(normalized.get("intent")).lower() == "factor_lookup":
        normalized["factor_type_hint"] = None

    return normalized