import json
import os
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
COMPLETE_PATH = DATA_DIR / "Complete-DB.xlsx"
FACTORS_PATH = DATA_DIR / "Factors-DB.xlsx"

st.set_page_config(page_title="Data Assistant", page_icon="💬", layout="wide")

API_KEY = os.getenv("GROQ_API_KEY", "")

if not API_KEY:
    st.warning("Add GROQ_API_KEY to your .env file first.")

SSL_CERT = os.getenv("SSL_CERT_FILE", False)
_http_client = httpx.Client(verify=SSL_CERT)
client = Groq(api_key=API_KEY, http_client=_http_client) if API_KEY else None


@st.cache_data
def load_data():
    complete = pd.read_excel(COMPLETE_PATH)
    factors = pd.read_excel(FACTORS_PATH)

    complete.columns = [str(c).strip() for c in complete.columns]
    factors.columns = [str(c).strip() for c in factors.columns]

    complete = complete.fillna("")
    factors = factors.fillna("")

    for col in complete.columns:
        if complete[col].dtype == object:
            complete[col] = complete[col].astype(str).str.strip()

    for col in factors.columns:
        if factors[col].dtype == object:
            factors[col] = factors[col].astype(str).str.strip()

    if "sequence" not in factors.columns:
        factors["sequence"] = range(1, len(factors) + 1)

    return complete, factors


complete_df, factors_df = load_data()

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi, I can answer from your Excel data. Ask me about a project, factor flow, brand, market, or dependent variable.",
        }
    ]

if "route_history" not in st.session_state:
    st.session_state.route_history = []

if "last_route" not in st.session_state:
    st.session_state.last_route = {}

if "last_projects" not in st.session_state:
    st.session_state.last_projects = pd.DataFrame()

if "last_factors" not in st.session_state:
    st.session_state.last_factors = pd.DataFrame()

if "last_retrieval_note" not in st.session_state:
    st.session_state.last_retrieval_note = "No retrieval yet. Ask a question to see retrieval output."


def safe_str(x):
    return "" if x is None else str(x).strip()


def build_catalog_text():
    cols = [c for c in ["CoEJobnumber", "BrandModelled", "MarketforBrand", "Dependentvar", "Category", "SubCategory", "Client"] if c in complete_df.columns]
    sample = complete_df[cols].head(20).to_dict(orient="records")
    return json.dumps(sample, ensure_ascii=False, indent=2)


def route_query(question, history):
    system_prompt = """
You are a routing engine for a data assistant.
Your job is NOT to answer the question.
Your job is to decide what the app should retrieve from the database.

Return only valid JSON with these keys:
{
  "intent": "project_lookup" | "factor_lookup" | "follow_up" | "summary" | "clarify",
    "brand_hint": string or null,
    "client_hint": string or null,
  "market_hint": string or null,
    "category_hint": string or null,
    "subcategory_hint": string or null,
    "dependent_var_hint": string or null,
  "factor_type_hint": string or null,
    "coe_job_number_hint": string or null,
    "brand_client_scope": "brand" | "client" | null,
    "category_scope": "category" | "subcategory" | null,
  "needs_followup_context": true or false,
  "clarification_question": string or null
}

Rules:
- If the user asks whether we worked on a project, use project_lookup.
- If the user asks for factors, order, flow, or type, use factor_lookup.
- If the user refers to "that", "same one", "what about", "those", use follow_up.
- If unsure, use clarify.
- Do not explain. Do not add markdown. Output JSON only.
"""

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-6:])
    messages.append({"role": "user", "content": question})

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0,
    )
    text = resp.choices[0].message.content.strip()
    default_route = {
        "intent": "clarify",
        "brand_hint": None,
        "client_hint": None,
        "market_hint": None,
        "category_hint": None,
        "subcategory_hint": None,
        "dependent_var_hint": None,
        "factor_type_hint": None,
        "coe_job_number_hint": None,
        "brand_client_scope": None,
        "category_scope": None,
        "needs_followup_context": False,
        "clarification_question": "Can you clarify which project, brand, or market you mean?",
    }
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return default_route
        merged = default_route.copy()
        merged.update(parsed)
        return merged
    except Exception:
        return default_route


def norm_text(value):
    return "".join(ch for ch in safe_str(value).lower() if ch.isalnum())


def contains_mask(df, col, hint):
    if col not in df.columns or not safe_str(hint):
        return pd.Series(False, index=df.index)
    needle = norm_text(hint)
    if not needle:
        return pd.Series(False, index=df.index)
    return df[col].astype(str).apply(lambda x: needle in norm_text(x))


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


def unique_project_options(df):
    cols = [c for c in ["BrandModelled", "MarketforBrand", "CoEJobnumber", "Client", "Category", "SubCategory"] if c in df.columns]
    opts = df[cols].drop_duplicates().head(12)
    lines = []
    for idx, row in enumerate(opts.to_dict(orient="records"), start=1):
        line_bits = []
        for c in ["BrandModelled", "MarketforBrand", "CoEJobnumber", "Client"]:
            if c in row and safe_str(row[c]):
                line_bits.append(f"{c}: {row[c]}")
        lines.append(f"{idx}. " + " | ".join(line_bits))
    return "\n".join(lines)


def filter_projects(route):
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
                    return df.iloc[0:0], "I found similar matches in both SubCategory and Category. Are you looking for SubCategory or Category?"
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
            if brand_mask.any() and client_mask.any():
                brand_vals = df.loc[brand_mask, "BrandModelled"].astype(str).unique().tolist() if "BrandModelled" in df.columns else []
                client_vals = df.loc[client_mask, "Client"].astype(str).unique().tolist() if "Client" in df.columns else []
                if values_are_similar(brand_vals, client_vals):
                    return df.iloc[0:0], "I found similar matches in both Brand and Client. Are you looking for Brand or Client?"
            if brand_mask.any():
                mask &= brand_mask
                used_filters += 1
            elif client_mask.any():
                mask &= client_mask
                used_filters += 1

    if used_filters == 0:
        return df.iloc[0:0], "Please share at least one detail such as brand, market, client, category, subcategory, DV, factor type, or CoE job number."

    return df[mask].copy(), None


def fetch_factors_for_projects(projects, route):
    if projects.empty:
        return factors_df.iloc[0:0].copy()

    rows = []
    for _, project_row in projects.iterrows():
        row_mask = pd.Series(True, index=factors_df.index)

        if "CoEJobnumber" in factors_df.columns and safe_str(project_row.get("CoEJobnumber", "")):
            row_mask &= factors_df["CoEJobnumber"].astype(str) == safe_str(project_row.get("CoEJobnumber", ""))
        if "BrandModelled" in factors_df.columns and safe_str(project_row.get("BrandModelled", "")):
            row_mask &= factors_df["BrandModelled"].astype(str).str.lower() == safe_str(project_row.get("BrandModelled", "")).lower()
        if "MarketforBrand" in factors_df.columns and safe_str(project_row.get("MarketforBrand", "")):
            row_mask &= factors_df["MarketforBrand"].astype(str).str.lower() == safe_str(project_row.get("MarketforBrand", "")).lower()

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


def factor_summary(fdf):
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


def format_factors_response(fdf):
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


def answer_with_groq(question, route, project_rows, factor_rows):
    if client is None:
        return "GROQ_API_KEY is missing."

    system_prompt = """
You are a conversational assistant answering only from the provided project and factor context.
Use a simple, scan-friendly format.

Formatting rules:
- Do not write long paragraphs.
- Start with one line: "Answer: Yes" or "Answer: No" or "Answer: Not enough data".
- Then provide 3-6 short bullet points.
- Keep each bullet to one short sentence.
- Include only facts present in context.
- If context is insufficient, add a bullet: "Missing: ...".
- Do not invent facts.
"""

    context = {
        "route": route,
        "projects": project_rows.to_dict(orient="records"),
        "factors": factor_rows.to_dict(orient="records"),
    }

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(st.session_state.messages[-8:])
    messages.append({"role": "user", "content": f"Question: {question}\n\nContext:\n{json.dumps(context, ensure_ascii=False)}"})

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()


st.title("Data Assistant")
st.caption("Chat with your Excel files like a conversational assistant.")

with st.sidebar:
    st.subheader("Retrieval output")
    st.caption("Latest retrieval trace from your most recent question")
    st.write(st.session_state.last_retrieval_note)

    if st.session_state.last_route:
        st.markdown("**Route JSON**")
        st.json(st.session_state.last_route)

    st.markdown("**Matched projects**")
    st.write(f"Rows: {len(st.session_state.last_projects)}")
    if not st.session_state.last_projects.empty:
        st.dataframe(st.session_state.last_projects, use_container_width=True, hide_index=True)

    st.markdown("**Matched factors**")
    st.write(f"Rows: {len(st.session_state.last_factors)}")
    if not st.session_state.last_factors.empty:
        st.dataframe(st.session_state.last_factors, use_container_width=True, hide_index=True)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("Ask a question about the database")

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    route = route_query(question, st.session_state.messages[:-1])
    st.session_state.route_history.append(route)
    st.session_state.last_route = route

    if route.get("intent") == "clarify":
        answer = route.get("clarification_question", "Can you clarify?")
        st.session_state.last_projects = pd.DataFrame()
        st.session_state.last_factors = pd.DataFrame()
        st.session_state.last_retrieval_note = "Routing requested clarification."
    else:
        candidates, clarify_msg = filter_projects(route)
        is_factor_query = route.get("intent") == "factor_lookup" or bool(route.get("factor_type_hint"))

        if clarify_msg:
            answer = clarify_msg
            st.session_state.last_projects = pd.DataFrame()
            st.session_state.last_factors = pd.DataFrame()
            st.session_state.last_retrieval_note = "Clarification needed due to ambiguous filters."
        elif candidates.empty:
            answer = "I could not find a matching project in the database."
            st.session_state.last_projects = pd.DataFrame()
            st.session_state.last_factors = pd.DataFrame()
            st.session_state.last_retrieval_note = "No project rows matched the current filters."
        elif is_factor_query and len(candidates.drop_duplicates()) > 1 and not safe_str(route.get("coe_job_number_hint", "")):
            options = unique_project_options(candidates)
            answer = (
                "I found multiple matching projects for factors. "
                "Please provide more detail (CoE job number, brand, market, or client).\n\n"
                f"Matches:\n{options}"
            )
            st.session_state.last_projects = candidates.copy()
            st.session_state.last_factors = pd.DataFrame()
            st.session_state.last_retrieval_note = "Multiple projects matched a factor query; awaiting disambiguation."
        else:
            factors = fetch_factors_for_projects(candidates, route) if is_factor_query else factors_df.iloc[0:0].copy()
            if is_factor_query:
                answer = format_factors_response(factors)
                st.session_state.last_retrieval_note = "Factor retrieval completed."
            else:
                answer = answer_with_groq(question, route, candidates, factors)
                st.session_state.last_retrieval_note = "Project retrieval completed and passed to answer model."
            st.session_state.last_projects = candidates.copy()
            st.session_state.last_factors = factors.copy()

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.write(answer)

    st.rerun()