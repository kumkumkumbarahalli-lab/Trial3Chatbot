from __future__ import annotations

import re
from typing import Iterable

import pandas as pd


MULTI_VALUE_COLUMNS = {
    "BrandModelled",
    "MarketforBrand",
    "Client",
    "ClientName",
    "Market",
    "Country",
}

MARKET_VALUE_COLUMNS = {
    "MarketforBrand",
    "Market",
    "Country",
}

COUNTRY_ALIASES = {
    "argentina": "Argentina",
    "australia": "Australia",
    "bangladesh": "Bangladesh",
    "belgium": "Belgium",
    "brazil": "Brazil",
    "canada": "Canada",
    "china": "China",
    "colombia": "Colombia",
    "columbia": "Colombia",
    "czechrepublic": "Czech Republic",
    "czechia": "Czech Republic",
    "egypt": "Egypt",
    "france": "France",
    "germany": "Germany",
    "greece": "Greece",
    "guatemala": "Guatemala",
    "guatemela": "Guatemala",
    "honduras": "Honduras",
    "india": "India",
    "indonesia": "Indonesia",
    "italy": "Italy",
    "japan": "Japan",
    "kenya": "Kenya",
    "ksa": "Saudi Arabia",
    "malaysia": "Malaysia",
    "mexico": "Mexico",
    "netherlands": "Netherlands",
    "newzealand": "New Zealand",
    "norway": "Norway",
    "pakistan": "Pakistan",
    "philippines": "Philippines",
    "poland": "Poland",
    "romania": "Romania",
    "russia": "Russia",
    "saudiarabia": "Saudi Arabia",
    "southafrica": "South Africa",
    "southkorea": "South Korea",
    "spain": "Spain",
    "srilanka": "Sri Lanka",
    "sweden": "Sweden",
    "switzerland": "Switzerland",
    "taiwan": "Taiwan",
    "tanzania": "Tanzania",
    "thailand": "Thailand",
    "turkey": "Turkey",
    "uae": "UAE",
    "uk": "UK",
    "ukraine": "Ukraine",
    "unitedarabemirates": "UAE",
    "unitedkingdom": "UK",
    "unitedstates": "USA",
    "unitedstatesofamerica": "USA",
    "usa": "USA",
    "us": "USA",
    "vietnam": "Vietnam",
}

CITY_TO_COUNTRY = {
    "ahmedabad": "India",
    "bangalore": "India",
    "baroda": "India",
    "bengaluru": "India",
    "bogota": "Colombia",
    "chennai": "India",
    "delhi": "India",
    "dubai": "UAE",
    "hyderabad": "India",
    "kolkata": "India",
    "madrid": "Spain",
    "mumbai": "India",
    "newdelhi": "India",
    "pune": "India",
    "saopaulo": "Brazil",
    "sãopaulo": "Brazil",
    "vadodara": "India",
}


def safe_str(value) -> str:
    return "" if value is None else str(value).strip()


def normalize_text(value) -> str:
    return "".join(ch for ch in safe_str(value).lower() if ch.isalnum())


def _split_outside_parentheses(raw: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0

    for ch in raw.replace(";", ","):
        if ch == "(":
            depth += 1
            current.append(ch)
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
            continue
        if ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def split_multi_values(value) -> list[str]:
    raw = safe_str(value)
    if not raw:
        return []
    return _split_outside_parentheses(raw)


def _clean_market_token(token: str) -> str:
    cleaned = safe_str(token).strip(" ,;\t\n\r")
    if cleaned.startswith("(") and ")" not in cleaned:
        cleaned = cleaned.lstrip("(").strip()
    if cleaned.endswith(")") and "(" not in cleaned:
        cleaned = cleaned.rstrip(")").strip()
    cleaned = re.sub(r"^[\[\s]+", "", cleaned)
    cleaned = re.sub(r"[\]\s]+$", "", cleaned)
    return cleaned.strip()


def _canonical_country_name(value: str) -> str | None:
    cleaned = _clean_market_token(value)
    if not cleaned:
        return None

    normalized = normalize_text(cleaned)
    if normalized in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[normalized]
    if normalized in CITY_TO_COUNTRY:
        return CITY_TO_COUNTRY[normalized]
    return None


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = normalize_text(value)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(value)
    return ordered


def normalize_market_values(value) -> list[str]:
    raw_tokens = split_multi_values(value)
    normalized_values: list[str] = []

    for raw_token in raw_tokens:
        token = _clean_market_token(raw_token)
        if not token:
            continue

        direct_country = _canonical_country_name(token)
        if direct_country:
            normalized_values.append(direct_country)
            continue

        prefix = token.split("(", 1)[0].strip()
        prefix_country = _canonical_country_name(prefix)
        if prefix_country:
            normalized_values.append(prefix_country)
            continue

        inner_matches = re.findall(r"\(([^)]*)\)", token)
        inner_countries: list[str] = []
        for inner in inner_matches:
            for piece in re.split(r"[,/;]", inner):
                country = _canonical_country_name(piece)
                if country:
                    inner_countries.append(country)

        if inner_countries:
            normalized_values.extend(inner_countries)
            continue

        normalized_values.append(token)

    return _dedupe_preserve_order(normalized_values)


def market_matches_hint(cell_value, hint_value) -> bool:
    needle_values = normalize_market_values(hint_value)
    haystack_values = normalize_market_values(cell_value)
    if not needle_values or not haystack_values:
        return False

    haystack_norm = {normalize_text(value) for value in haystack_values if normalize_text(value)}
    for needle in needle_values:
        needle_norm = normalize_text(needle)
        if needle_norm and needle_norm in haystack_norm:
            return True
    return False


def cell_matches_hint(cell_value, hint_value, is_multi_value: bool = False) -> bool:
    needle = normalize_text(hint_value)
    if not needle:
        return False

    if is_multi_value:
        tokens = [normalize_text(token) for token in split_multi_values(cell_value)]
        tokens = [token for token in tokens if token]

        if len(needle) < 3:
            return needle in tokens

        return any(token == needle or needle in token or token in needle for token in tokens)

    hay = normalize_text(cell_value)
    if len(needle) < 3:
        return hay == needle
    return needle in hay


def series_for_counts(
    df: pd.DataFrame,
    column: str | None,
    multi_value_columns: Iterable[str] = MULTI_VALUE_COLUMNS,
) -> pd.Series:
    if not column:
        return pd.Series(dtype="object")

    series = df[column].astype(str).str.strip()
    series = series[series != ""]

    if column in MARKET_VALUE_COLUMNS:
        series = series.apply(normalize_market_values).explode().dropna()
        series = series.astype(str).str.strip()
        series = series[series != ""]
    elif column in set(multi_value_columns):
        series = series.apply(split_multi_values).explode().dropna()
        series = series.astype(str).str.strip()
        series = series[series != ""]

    return series