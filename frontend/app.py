"""
Phase 7 — Streamlit SaaS Frontend
Infra Feasibility AI — Global Group of Companies
"""
import streamlit as st
import requests
import json
import plotly.graph_objects as go
import pandas as pd

API_BASE = "http://backend:8000"

st.set_page_config(
    page_title="Infra Feasibility AI — GGC",
    page_icon="🌍",
    layout="wide",
)

# ─── Session State ─────────────────────────────────────────────
if "token" not in st.session_state:
    st.session_state.token = None
if "username" not in st.session_state:
    st.session_state.username = None


def auth_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


# ─── Auth Page ────────────────────────────────────────────────
if not st.session_state.token:
    st.title("Infra Feasibility AI")
    st.caption("Global Group of Companies — www.ggcuk.com")
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                resp = requests.post(
                    f"{API_BASE}/auth/token",
                    data={"username": username, "password": password},
                )
                if resp.status_code == 200:
                    st.session_state.token = resp.json()["access_token"]
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid credentials")

    with tab_signup:
        with st.form("signup_form"):
            email = st.text_input("Email")
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            if st.form_submit_button("Create Account"):
                resp = requests.post(
                    f"{API_BASE}/auth/signup",
                    json={"email": email, "username": new_username, "password": new_password},
                )
                if resp.status_code == 201:
                    st.success("Account created. Please login.")
                else:
                    st.error(resp.json().get("detail", "Error"))
    st.stop()


# ─── Main Platform ────────────────────────────────────────────
st.sidebar.title("Infra Feasibility AI")
st.sidebar.caption(f"Logged in as: {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.token = None
    st.rerun()

page = st.sidebar.radio("Navigation", ["New Project", "My Projects", "Run Analysis", "View Reports"])


if page == "New Project":
    st.header("Create New Project")
    with st.form("new_project"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Project Name", "Iraq Solar Farm 200MW")
            project_type = st.selectbox("Project Type", ["solar", "wind", "hydro", "thermal"])
            country_code = st.text_input("Country Code (ISO-3)", "IRQ")
            capacity_mw = st.number_input("Installed Capacity (MW)", min_value=1.0, value=200.0)
        with col2:
            capex_usd = st.number_input("Total CAPEX (USD)", min_value=100000.0, value=200_000_000.0, step=1_000_000.0)
            electricity_price = st.number_input("Electricity Price (USD/MWh)", min_value=10.0, value=65.0)
            latitude = st.number_input("Latitude", value=33.3)
            longitude = st.number_input("Longitude", value=44.4)
            life_years = st.number_input("Project Life (Years)", min_value=5, max_value=40, value=25)
        description = st.text_area("Description")

        if st.form_submit_button("Save Project"):
            resp = requests.post(
                f"{API_BASE}/projects",
                json={
                    "name": name, "description": description,
                    "project_type": project_type, "country_code": country_code,
                    "latitude": latitude, "longitude": longitude,
                    "capacity_mw": capacity_mw, "capex_usd": capex_usd,
                    "electricity_price_usd_mwh": electricity_price,
                    "project_life_years": life_years,
                },
                headers=auth_headers(),
            )
            if resp.status_code == 201:
                st.success(f"Project created: ID {resp.json()['id']}")
            else:
                st.error(resp.text)


elif page == "My Projects":
    st.header("My Projects")
    resp = requests.get(f"{API_BASE}/projects", headers=auth_headers())
    if resp.status_code == 200:
        projects = resp.json()
        if projects:
            df = pd.DataFrame(projects)
            st.dataframe(df[["id", "name", "country_code", "capacity_mw", "capex_usd"]], use_container_width=True)
        else:
            st.info("No projects yet. Create one using the New Project tab.")
    else:
        st.error("Failed to load projects")


elif page == "Run Analysis":
    st.header("Run Full Analysis")
    resp = requests.get(f"{API_BASE}/projects", headers=auth_headers())
    projects = resp.json() if resp.status_code == 200 else []
    if not projects:
        st.warning("No projects found. Create a project first.")
    else:
        project_options = {f"{p['name']} (ID: {p['id']})": p["id"] for p in projects}
        selected = st.selectbox("Select Project", list(project_options.keys()))
        project_id = project_options[selected]
        if st.button("Run Full Analysis", type="primary"):
            with st.spinner("Running analysis — fetching live data, modelling energy system, calculating financials..."):
                resp = requests.post(f"{API_BASE}/analyze/{project_id}", headers=auth_headers())
            if resp.status_code == 200:
                st.session_state["last_report"] = resp.json()
                st.success("Analysis complete. View results in View Reports.")
                st.json(resp.json().get("financials", {}))
            else:
                st.error(f"Analysis failed: {resp.text}")


elif page == "View Reports":
    st.header("Analysis Reports")
    report = st.session_state.get("last_report")
    if not report:
        st.info("Run an analysis first.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs(["Executive Summary", "Financials", "Scenarios", "Risk"])

        with tab1:
            st.text(report.get("executive_summary", ""))

        with tab2:
            fin = report.get("financials", {})
            mc = report.get("monte_carlo", {})
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("NPV (USD)", f"${fin.get('npv_usd', 0):,.0f}")
            col2.metric("IRR", f"{fin.get('irr_pct', 0):.1f}%")
            col3.metric("LCOE (USD/MWh)", f"${fin.get('lcoe_usd_mwh', 0):.2f}")
            col4.metric("Payback", f"{fin.get('payback_years', 0):.1f} yrs")
            if mc:
                st.subheader("Monte Carlo NPV Distribution")
                npv_mc = mc.get("npv", {})
                fig = go.Figure(go.Indicator(
                    mode="number+gauge+delta",
                    value=npv_mc.get("p50", 0),
                    delta={"reference": npv_mc.get("mean", 0)},
                    title={"text": "NPV P50 (USD)"},
                    gauge={"axis": {"range": [npv_mc.get("p10", 0), npv_mc.get("p90", 0)]}},
                ))
                st.plotly_chart(fig, use_container_width=True)
                st.caption(f"Probability of positive NPV: {npv_mc.get('prob_positive', 0):.1f}%")

        with tab3:
            scenarios = report.get("scenarios", {})
            if scenarios:
                rows = []
                for name, s in scenarios.items():
                    rows.append({
                        "Scenario": name.capitalize(),
                        "NPV (USD)": f"${s['npv_usd']:,.0f}",
                        "IRR (%)": s["irr_pct"],
                        "LCOE (USD/MWh)": s["lcoe_usd_mwh"],
                        "Payback (yrs)": s["payback_years"],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True)

            sensitivity = report.get("sensitivity", [])
            if sensitivity:
                st.subheader("Tornado Chart — NPV Sensitivity")
                variables = [s["variable"] for s in sensitivity]
                low_vals = [s["low_npv"] for s in sensitivity]
                high_vals = [s["high_npv"] for s in sensitivity]
                fig = go.Figure()
                fig.add_bar(name="-20%", y=variables, x=low_vals, orientation="h", marker_color="crimson")
                fig.add_bar(name="+20%", y=variables, x=high_vals, orientation="h", marker_color="steelblue")
                fig.update_layout(barmode="overlay", title="NPV Sensitivity Tornado Chart")
                st.plotly_chart(fig, use_container_width=True)

        with tab4:
            risk = report.get("risk", {})
            st.metric("Country Risk Score", f"{risk.get('composite_risk_score', 'N/A')}/100")
            st.metric("Risk Label", risk.get("risk_label", "N/A"))
            st.metric("Risk-Adjusted Discount Rate", f"{risk.get('risk_adjusted_discount_rate_pct', 'N/A')}%")
            components = risk.get("component_scores", {})
            if components:
                fig = go.Figure(go.Bar(
                    x=list(components.keys()),
                    y=list(components.values()),
                    marker_color=["green" if v >= 60 else "orange" if v >= 40 else "red" for v in components.values()],
                ))
                fig.update_layout(title="Country Risk Component Scores (0–100)", yaxis_range=[0, 100])
                st.plotly_chart(fig, use_container_width=True)

        st.download_button(
            "Download Full Report JSON",
            data=json.dumps(report, indent=2, default=str),
            file_name="infra_feasibility_report.json",
            mime="application/json",
        )
