"""
BioInsight — Streamlit frontend.

Tabs:
  1. Upload      — genomic file + blood CSV upload with sample downloads
  2. Insights    — domain-level health insights (lifestyle recommendations)
  3. Disease Risk — ranked disease risk panel powered by Open Targets + ClinVar
"""

import json
import os
import pathlib
import httpx
import streamlit as st

# Reads BIOINSIGHT_API_URL from:
#   1. Streamlit Cloud secrets (st.secrets) — set in the app dashboard
#   2. Environment variable — set in .env or platform env vars
#   3. Localhost fallback for local development
def _get_api_base() -> str:
    # 1. Env var first — works for Fly.io, Docker, and local .env
    from_env = os.getenv("BIOINSIGHT_API_URL")
    if from_env:
        return from_env.rstrip("/")
    # 2. Streamlit Cloud secrets — only attempted when no env var is present
    try:
        val = st.secrets.get("BIOINSIGHT_API_URL")
        if val:
            return str(val).rstrip("/")
    except Exception:
        pass
    # 3. Local dev fallback
    return "http://localhost:8000"

API_BASE = _get_api_base()
DATA_DIR = pathlib.Path(__file__).parent.parent / "data"

st.set_page_config(
    page_title="BioInsight",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state init ───────────────────────────────────────────────────────
for key in ("enriched_variants", "biomarkers", "insights", "disease_risks", "upload_errors"):
    if key not in st.session_state:
        st.session_state[key] = [] if key in ("enriched_variants", "insights", "disease_risks", "upload_errors") else {}


# ── Helper: display error detail from API ───────────────────────────────────
def show_api_error(resp: httpx.Response) -> None:
    try:
        detail = resp.json().get("detail", {})
        if isinstance(detail, dict):
            st.error(f"**{detail.get('error', 'Error')}:** {detail.get('message', 'Unknown error')}")
            if detail.get("hint"):
                st.info(f"💡 Hint: {detail['hint']}")
            if detail.get("parse_errors"):
                with st.expander("Parse errors"):
                    for e in detail["parse_errors"]:
                        st.warning(e)
        else:
            st.error(str(detail))
    except Exception:
        st.error(f"HTTP {resp.status_code}: {resp.text[:300]}")


# ── Header ───────────────────────────────────────────────────────────────────
st.title("🧬 BioInsight")
st.caption(
    "Upload your genomic data and blood results to receive integrated, "
    "evidence-based disease risk scores and lifestyle recommendations."
)
st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_upload, tab_insights, tab_risks = st.tabs(
    ["📂 Upload Data", "💡 Health Insights", "⚠️ Disease Risk"]
)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — UPLOAD DATA
# ════════════════════════════════════════════════════════════════════════════
with tab_upload:
    col_gen, col_blood = st.columns(2, gap="large")

    # ── Genomic Upload ───────────────────────────────────────────────────────
    with col_gen:
        st.subheader("🧬 Genomic File")
        st.markdown(
            "Upload a **23andMe raw data export** (`.txt`) or a **VCF file** (`.vcf`). "
            "Only rs# variants are processed."
        )

        # Sample file download
        sample_genomic = DATA_DIR / "sample_genomic.txt"
        if sample_genomic.exists():
            st.download_button(
                label="⬇️ Download sample_genomic.txt",
                data=sample_genomic.read_bytes(),
                file_name="sample_genomic.txt",
                mime="text/plain",
                help="Use this sample file to test the app without a real genomic file.",
            )

        genomic_file = st.file_uploader(
            "Upload genomic file",
            type=["txt", "vcf"],
            key="genomic_uploader",
            label_visibility="collapsed",
        )

        if genomic_file:
            st.caption(f"📄 {genomic_file.name} — {genomic_file.size / 1024:.1f} KB")

        if st.button("🔬 Analyse Genomic File", disabled=not genomic_file, type="primary"):
            with st.spinner("Parsing variants and querying NCBI ClinVar..."):
                try:
                    resp = httpx.post(
                        f"{API_BASE}/genomics/upload",
                        files={"file": (genomic_file.name, genomic_file.getvalue())},
                        timeout=180,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.enriched_variants = data["enriched"]
                        st.success(
                            f"✅ {data['variant_count']} variants parsed · "
                            f"{data['clinvar_hits']} ClinVar hits"
                        )
                        if data.get("parse_warnings"):
                            with st.expander(f"⚠️ {len(data['parse_warnings'])} parse warnings"):
                                for w in data["parse_warnings"]:
                                    st.warning(w)
                    else:
                        show_api_error(resp)
                except httpx.ConnectError:
                    st.error("❌ Cannot reach the backend. Is FastAPI running on port 8000?")
                except Exception as e:
                    st.error(f"Unexpected error: {e}")

        # Status badge
        if st.session_state.enriched_variants:
            st.success(f"✅ {len(st.session_state.enriched_variants)} variants loaded")
        else:
            st.info("No genomic data loaded yet.")

    # ── Blood Upload ─────────────────────────────────────────────────────────
    with col_blood:
        st.subheader("🩸 Blood Results")
        st.markdown(
            "Upload a **CSV file** with your lab results. "
            "Required columns: `marker`, `value`. Optional: `unit`."
        )

        # Sample file download
        sample_blood = DATA_DIR / "sample_blood.csv"
        if sample_blood.exists():
            st.download_button(
                label="⬇️ Download sample_blood.csv",
                data=sample_blood.read_bytes(),
                file_name="sample_blood.csv",
                mime="text/csv",
                help="Use this sample file to test the app without real lab results.",
            )

        blood_source = st.radio(
            "Data source",
            ["Upload CSV", "Manual Entry", "Quest Diagnostics (OAuth)"],
            horizontal=True,
        )

        # ── CSV Upload ───────────────────────────────────────────────────────
        if blood_source == "Upload CSV":
            blood_file = st.file_uploader(
                "Upload blood CSV",
                type=["csv"],
                key="blood_uploader",
                label_visibility="collapsed",
            )

            if blood_file:
                st.caption(f"📄 {blood_file.name} — {blood_file.size / 1024:.1f} KB")

            if st.button("🩺 Process Blood Results", disabled=not blood_file, type="primary"):
                with st.spinner("Parsing blood results..."):
                    try:
                        resp = httpx.post(
                            f"{API_BASE}/blood/upload",
                            files={"file": (blood_file.name, blood_file.getvalue())},
                            timeout=30,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state.biomarkers = data["biomarkers"]
                            st.success(
                                f"✅ {data['marker_count']} markers loaded from {data['row_count']} rows"
                            )
                            if data.get("warnings"):
                                with st.expander(f"⚠️ {len(data['warnings'])} warnings"):
                                    for w in data["warnings"]:
                                        st.warning(w)
                            if data.get("parse_errors"):
                                with st.expander(f"❌ {len(data['parse_errors'])} row errors"):
                                    for e in data["parse_errors"]:
                                        st.error(e)
                        else:
                            show_api_error(resp)
                    except httpx.ConnectError:
                        st.error("❌ Cannot reach the backend. Is FastAPI running on port 8000?")
                    except Exception as e:
                        st.error(f"Unexpected error: {e}")

        # ── Manual Entry ─────────────────────────────────────────────────────
        elif blood_source == "Manual Entry":
            with st.form("manual_blood_form"):
                MANUAL_MARKERS = [
                    "LDL Cholesterol", "HDL Cholesterol", "Total Cholesterol",
                    "HbA1c", "Blood Glucose", "Triglycerides",
                    "CRP (C-Reactive Protein)", "Vitamin D (25-OH)", "Vitamin B12",
                    "Ferritin", "TSH", "ALT", "Creatinine",
                ]
                cols = st.columns(2)
                manual_vals: dict[str, float] = {}
                for i, marker in enumerate(MANUAL_MARKERS):
                    val = cols[i % 2].number_input(marker, value=0.0, min_value=0.0, step=0.1, key=f"m_{marker}")
                    if val > 0:
                        manual_vals[marker] = val

                if st.form_submit_button("💾 Save Manual Entries", type="primary"):
                    if not manual_vals:
                        st.warning("Enter at least one marker value greater than 0.")
                    else:
                        try:
                            resp = httpx.post(
                                f"{API_BASE}/blood/manual",
                                json={"markers": manual_vals},
                                timeout=10,
                            )
                            if resp.status_code == 200:
                                st.session_state.biomarkers = resp.json()["biomarkers"]
                                st.success(f"✅ {len(manual_vals)} markers saved.")
                            else:
                                show_api_error(resp)
                        except Exception as e:
                            st.error(f"Error: {e}")

        # ── Quest OAuth ──────────────────────────────────────────────────────
        else:
            st.info("Connect your Quest Diagnostics account to pull live FHIR lab results.")
            quest_url = (
                "https://oauth.questdiagnostics.com/authorize"
                "?response_type=code"
                "&client_id=YOUR_CLIENT_ID"
                "&redirect_uri=http://localhost:8000/blood/quest/callback"
                "&scope=patient/DiagnosticReport.read"
            )
            st.link_button("🔗 Connect Quest Diagnostics", quest_url)
            oauth_code = st.text_input("Paste OAuth code from redirect URL", type="password")
            if st.button("Fetch Lab Results", disabled=not oauth_code):
                with st.spinner("Fetching Quest FHIR data..."):
                    try:
                        resp = httpx.post(
                            f"{API_BASE}/blood/quest/callback",
                            json={"code": oauth_code, "state": ""},
                            timeout=60,
                        )
                        if resp.status_code == 200:
                            st.session_state.biomarkers = resp.json()["biomarkers"]
                            st.success(f"✅ {len(st.session_state.biomarkers)} biomarkers loaded.")
                        else:
                            show_api_error(resp)
                    except Exception as e:
                        st.error(f"Error: {e}")

        # Status badge
        if st.session_state.biomarkers:
            abnormal = sum(
                1 for v in st.session_state.biomarkers.values()
                if isinstance(v, dict) and v.get("status") != "normal"
            )
            st.success(f"✅ {len(st.session_state.biomarkers)} markers loaded · {abnormal} abnormal")
        else:
            st.info("No blood data loaded yet.")

    # ── Generate Button ──────────────────────────────────────────────────────
    st.divider()
    ready = bool(st.session_state.enriched_variants or st.session_state.biomarkers)
    if not ready:
        st.info("Upload at least one data source above, then click Generate.")

    if st.button(
        "🚀 Generate Insights & Disease Risks",
        disabled=not ready,
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("Running integration engine and querying Open Targets..."):
            try:
                resp = httpx.post(
                    f"{API_BASE}/insights/generate",
                    json={
                        "enriched_variants": st.session_state.enriched_variants,
                        "biomarkers": st.session_state.biomarkers,
                    },
                    timeout=90,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.insights = data["insights"]
                    st.session_state.disease_risks = data.get("disease_risks", [])
                    if data.get("disease_risk_warning"):
                        st.warning(f"Disease risk: {data['disease_risk_warning']}")
                    st.success(
                        f"✅ {len(st.session_state.insights)} domain insights · "
                        f"{len(st.session_state.disease_risks)} disease risks identified. "
                        "See the tabs above →"
                    )
                else:
                    show_api_error(resp)
            except httpx.ConnectError:
                st.error("❌ Cannot reach the backend. Is FastAPI running on port 8000?")
            except Exception as e:
                st.error(f"Unexpected error: {e}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — HEALTH INSIGHTS
# ════════════════════════════════════════════════════════════════════════════
with tab_insights:
    if not st.session_state.insights:
        st.info("No insights yet — upload data and click **Generate Insights & Disease Risks**.")
    else:
        CONF_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}
        CONF_LABEL = {"high": "High Priority", "medium": "Moderate Priority", "low": "Low Priority"}

        for insight in st.session_state.insights:
            domain = insight["domain"].replace("_", " ").title()
            conf = insight["confidence"]
            icon = CONF_ICON.get(conf, "⚪")
            label = CONF_LABEL.get(conf, conf.title())

            with st.expander(f"{icon} **{domain}** — {label}", expanded=(conf == "high")):
                c1, c2 = st.columns(2, gap="medium")

                with c1:
                    st.markdown("**🩸 Blood Markers**")
                    bm = insight.get("all_biomarkers", {})
                    if bm:
                        for name, info in bm.items():
                            if isinstance(info, dict):
                                status = info.get("status", "?")
                                value = info.get("value", "?")
                                unit = info.get("unit", "")
                                flag = "⚠️" if status != "normal" else "✅"
                                st.write(f"{flag} **{name}:** {value} {unit} _{status}_")
                    else:
                        st.caption("No blood data for this domain.")

                with c2:
                    st.markdown("**🧬 Genetic Variants**")
                    variants = insight.get("risk_variants", [])
                    if variants:
                        for v in variants[:6]:
                            sig = v.get("significance", "?")
                            gene = v.get("gene", "?")
                            st.write(f"**{v['rsid']}** ({gene}) — _{sig}_")
                            if v.get("traits"):
                                st.caption(", ".join(v["traits"][:3]))
                    else:
                        st.caption("No risk variants found for this domain.")

                st.markdown("**💡 Lifestyle Recommendations**")
                for rec in insight.get("recommendations", []):
                    st.markdown(f"- {rec}")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — DISEASE RISK
# ════════════════════════════════════════════════════════════════════════════
with tab_risks:
    if not st.session_state.disease_risks:
        st.info("No disease risks computed yet — upload data and click **Generate Insights & Disease Risks**.")
    else:
        RISK_ICON = {"high": "🔴", "moderate": "🟠", "low": "🟡"}
        RISK_COLOR = {"high": "#ffcccc", "moderate": "#ffe5cc", "low": "#fffacc"}

        high = [r for r in st.session_state.disease_risks if r["risk_level"] == "high"]
        moderate = [r for r in st.session_state.disease_risks if r["risk_level"] == "moderate"]
        low = [r for r in st.session_state.disease_risks if r["risk_level"] == "low"]

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Diseases Identified", len(st.session_state.disease_risks))
        m2.metric("🔴 High Risk", len(high))
        m3.metric("🟠 Moderate Risk", len(moderate))
        m4.metric("🟡 Low Risk", len(low))
        st.divider()

        # Disclaimer
        st.warning(
            "⚠️ **Disclaimer:** Disease risk scores are derived from population-level genomic research "
            "and blood biomarker reference ranges. They are **not a clinical diagnosis**. "
            "Consult your doctor before making any health decisions."
        )

        def render_risk_section(risks: list[dict], section_label: str, expanded: bool) -> None:
            if not risks:
                return
            st.subheader(section_label)
            for risk in risks:
                icon = RISK_ICON.get(risk["risk_level"], "⚪")
                score_pct = int(risk["combined_score"] * 100)
                label = f"{icon} **{risk['disease']}** — Evidence score: {score_pct}%"

                with st.expander(label, expanded=expanded):
                    sc1, sc2, sc3 = st.columns(3)
                    sc1.metric("Combined Score", f"{score_pct}%")
                    sc2.metric("Genetic Score", f"{int(risk['genetic_score'] * 100)}%")
                    sc3.metric("Blood Score", f"{int(risk['blood_score'] * 100)}%")

                    st.progress(risk["combined_score"], text=f"Evidence strength: {score_pct}%")

                    d1, d2 = st.columns(2)
                    with d1:
                        if risk.get("contributing_genes"):
                            st.markdown(f"**Genes:** {', '.join(risk['contributing_genes'])}")
                        if risk.get("contributing_variants"):
                            st.markdown(f"**Variants:** {', '.join(risk['contributing_variants'])}")
                        if risk.get("therapeutic_areas"):
                            st.markdown(f"**Area:** {', '.join(risk['therapeutic_areas'])}")

                    with d2:
                        if risk.get("contributing_biomarkers"):
                            st.markdown(f"**Abnormal markers:** {', '.join(risk['contributing_biomarkers'])}")
                        if risk.get("evidence_types"):
                            st.markdown(f"**Evidence:** {', '.join(risk['evidence_types'])}")

                    if risk.get("curated_notes"):
                        for note in risk["curated_notes"]:
                            st.info(f"📌 {note}")

        render_risk_section(high, "🔴 High Risk Diseases", expanded=True)
        render_risk_section(moderate, "🟠 Moderate Risk Diseases", expanded=False)
        render_risk_section(low, "🟡 Low Risk Diseases", expanded=False)

        st.divider()
        st.caption(
            "Data sources: [NCBI ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/) · "
            "[Open Targets Platform](https://platform.opentargets.org/) · "
            "Curated SNP-disease associations from published GWAS literature."
        )
