"""
FinSight AI - Streamlit Dashboard
Unified visualization for the NLP Risk Engine + Module A + Module B.

Pages:
  1. 🏠 Overview          — Live signal feed + KPI cards
  2. 📡 Risk Signals       — Searchable signal table + charts
  3. ⚖️  Index Rebalancer  — Module A: live weight visualization
  4. 🔥 Stress Testing     — Module B: scenario comparison + waterfall
  5. 🔬 Analyze Text       — On-demand NLP analysis playground
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import random

# Ensure root is importable
ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Project imports ────────────────────────────────────────────────────────
from src.engine.database import (
    initialize_db, get_recent_signals, get_rebalance_history,
    get_stress_test_history,
)
from src.engine.ingestion import ingest_all
from src.engine.nlp_analyzer import analyze, analyze_batch
from src.module_a.rebalancer import get_rebalancer, run_rebalancer, MOCK_INDEX
from src.module_b.portfolio import SyntheticPortfolio, SHOCK_SCENARIOS
from src.module_b.stress_test import get_stress_engine, run_stress_tests

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinSight AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
        letter-spacing: -0.5px;
    }
    .kpi-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.2rem 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .kpi-value { font-size: 2.2rem; font-weight: 800; }
    .kpi-label { font-size: 0.85rem; opacity: 0.9; margin-top: 0.2rem; }
    .signal-positive { color: #00c851; font-weight: 600; }
    .signal-negative { color: #ff4444; font-weight: 600; }
    .signal-neutral  { color: #ffbb33; font-weight: 600; }
    .stAlert { border-radius: 8px; }
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 1rem;
        border: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
</style>
""", unsafe_allow_html=True)


# ============================================================================
# Session state & initialization
# ============================================================================

@st.cache_resource
def init_app():
    initialize_db()
    return True


init_app()

if "signals" not in st.session_state:
    st.session_state.signals = []
if "rebalancer" not in st.session_state:
    st.session_state.rebalancer = get_rebalancer()
if "stress_engine" not in st.session_state:
    st.session_state.stress_engine = get_stress_engine()


# ============================================================================
# Sidebar
# ============================================================================

with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/S%26P_Global_logo.svg/320px-S%26P_Global_logo.svg.png",
        use_container_width=True,
    )
    st.markdown("---")
    st.markdown("## ⚙️ Controls")

    page = st.selectbox(
        "Navigate to",
        [
            "🏠 Overview",
            "📡 Risk Signals",
            "⚖️  Index Rebalancer",
            "🔥 Stress Testing",
            "🔬 Analyze Text",
        ],
    )

    st.markdown("---")
    st.markdown("### 🔄 Data Ingestion")

    offline_mode = st.toggle("Offline / Demo Mode", value=True,
                             help="Use synthetic data without network calls")

    n_social = st.slider("Synthetic posts", 10, 80, 40, step=5)

    if st.button("🚀 Run Full Pipeline", use_container_width=True, type="primary"):
        with st.spinner("Ingesting & analyzing data …"):
            items = ingest_all(
                rss=not offline_mode,
                social=True,
                from_disk=False,
                max_rss=6,
                n_social=n_social,
            )
            signals = analyze_batch(items, verbose=False)
            from src.engine.database import insert_signal
            for sig in signals:
                sig["id"] = insert_signal(sig)

            st.session_state.signals = signals
            rb = run_rebalancer(signals)
            st.session_state.rebalancer = rb
            eng = run_stress_tests(signals)
            st.session_state.stress_engine = eng
        st.success(f"✅ {len(signals)} signals processed!")
        st.rerun()

    st.markdown("---")
    st.caption("FinSight AI v1.0.0")
    st.caption("S&P Global & Crisil Hackathon 2026")
    st.caption("Nitish Jindal | IIT Kharagpur")


# ============================================================================
# Helpers
# ============================================================================

def load_signals_from_db(limit: int = 200) -> pd.DataFrame:
    rows = get_recent_signals(limit=limit)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df


def sentiment_badge(label: str) -> str:
    colors = {"positive": "🟢", "negative": "🔴", "neutral": "🟡"}
    return f"{colors.get(label, '⚪')} {label.title()}"


def make_gauge(value: float, title: str, max_val: float = 10) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={"text": title, "font": {"size": 14}},
        gauge={
            "axis": {"range": [0, max_val]},
            "bar": {"color": "#667eea"},
            "steps": [
                {"range": [0, 3],  "color": "#e8f5e9"},
                {"range": [3, 7],  "color": "#fff3e0"},
                {"range": [7, 10], "color": "#ffebee"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 3},
                "thickness": 0.75,
                "value": 7.0,
            },
        },
    ))
    fig.update_layout(height=220, margin=dict(l=20, r=20, t=40, b=10))
    return fig


# ============================================================================
# PAGE 1 — OVERVIEW
# ============================================================================

if page == "🏠 Overview":
    st.markdown(
        '<div class="main-header">📊 FinSight AI — Real-Time Financial Risk Intelligence</div>',
        unsafe_allow_html=True,
    )

    df = load_signals_from_db()

    if df.empty:
        st.info(
            "👈 No signals yet. Click **🚀 Run Full Pipeline** in the sidebar to generate risk signals.",
            icon="ℹ️",
        )
    else:
        # KPI row
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("Total Signals", len(df), delta=None)
        with c2:
            neg_pct = (df["sentiment_label"] == "negative").mean() * 100
            st.metric("Negative Sentiment", f"{neg_pct:.1f}%")
        with c3:
            high_risk = (df["impact_score"] >= 7).sum()
            st.metric("High-Impact Events", int(high_risk))
        with c4:
            avg_impact = df["impact_score"].mean()
            st.metric("Avg Impact Score", f"{avg_impact:.2f}")
        with c5:
            n_tickers = df["ticker"].nunique()
            st.metric("Tickers Covered", int(n_tickers))

        st.markdown("---")
        col_left, col_right = st.columns([3, 2])

        # ── Left: Sentiment over time ──────────────────────────────────────
        with col_left:
            st.subheader("📈 Sentiment Score Timeline")
            if "timestamp" in df.columns:
                df_ts = df.dropna(subset=["timestamp"]).sort_values("timestamp")
                fig_ts = px.scatter(
                    df_ts, x="timestamp", y="sentiment_score",
                    color="sentiment_label",
                    color_discrete_map={
                        "positive": "#00c851", "negative": "#ff4444", "neutral": "#ffbb33"
                    },
                    size="impact_score",
                    hover_data=["ticker", "event_type", "impact_score", "source"],
                    labels={"sentiment_score": "Sentiment Score", "timestamp": "Time"},
                )
                fig_ts.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)
                fig_ts.update_layout(height=350, showlegend=True, plot_bgcolor="#fafafa")
                st.plotly_chart(fig_ts, use_container_width=True)

        # ── Right: Event type distribution ────────────────────────────────
        with col_right:
            st.subheader("🗂️ Event Type Distribution")
            event_counts = df["event_type"].value_counts()
            fig_pie = px.pie(
                values=event_counts.values,
                names=event_counts.index,
                hole=0.45,
                color_discrete_sequence=px.colors.qualitative.Set3,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            fig_pie.update_layout(height=350, showlegend=True)
            st.plotly_chart(fig_pie, use_container_width=True)

        # ── Impact score distribution ──────────────────────────────────────
        st.subheader("⚡ Impact Score Distribution by Event Type")
        fig_box = px.box(
            df, x="event_type", y="impact_score",
            color="event_type",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            points="all",
        )
        fig_box.add_hline(y=7, line_dash="dot", line_color="red",
                          annotation_text="Stress Trigger (7.0)", annotation_position="top left")
        fig_box.update_layout(height=380, showlegend=False, xaxis_tickangle=-30)
        st.plotly_chart(fig_box, use_container_width=True)

        # ── Recent signals table ───────────────────────────────────────────
        st.subheader("📋 Recent Signals (Latest 10)")
        display_cols = [
            "timestamp", "ticker", "source", "sentiment_label",
            "sentiment_score", "event_type", "impact_score", "headline"
        ]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].head(10).reset_index(drop=True),
            use_container_width=True,
            column_config={
                "sentiment_score": st.column_config.NumberColumn("Sentiment", format="%.3f"),
                "impact_score":    st.column_config.ProgressColumn(
                    "Impact", min_value=0, max_value=10, format="%.1f"
                ),
                "headline":        st.column_config.TextColumn("Headline", width="large"),
            },
        )


# ============================================================================
# PAGE 2 — RISK SIGNALS
# ============================================================================

elif page == "📡 Risk Signals":
    st.title("📡 Risk Signal Feed")

    df = load_signals_from_db(limit=500)
    if df.empty:
        st.warning("No signals found. Run the pipeline first.")
        st.stop()

    # Filters
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker_filter = st.multiselect(
            "Filter by Ticker",
            sorted(df["ticker"].dropna().unique()),
        )
    with c2:
        event_filter = st.multiselect(
            "Filter by Event Type",
            sorted(df["event_type"].unique()),
        )
    with c3:
        sentiment_filter = st.multiselect(
            "Filter by Sentiment",
            ["positive", "negative", "neutral"],
        )

    impact_range = st.slider("Impact Score Range", 0.0, 10.0, (0.0, 10.0), 0.5)

    filtered = df.copy()
    if ticker_filter:
        filtered = filtered[filtered["ticker"].isin(ticker_filter)]
    if event_filter:
        filtered = filtered[filtered["event_type"].isin(event_filter)]
    if sentiment_filter:
        filtered = filtered[filtered["sentiment_label"].isin(sentiment_filter)]
    filtered = filtered[
        filtered["impact_score"].between(impact_range[0], impact_range[1])
    ]

    st.caption(f"Showing {len(filtered)} signals")

    # Heatmap: sentiment by ticker & event
    st.subheader("🗺️ Sentiment Heatmap by Ticker × Event Type")
    if not filtered.empty and "ticker" in filtered.columns:
        pivot = filtered.pivot_table(
            values="sentiment_score",
            index="ticker",
            columns="event_type",
            aggfunc="mean",
        )
        if not pivot.empty:
            fig_heat = px.imshow(
                pivot,
                color_continuous_scale="RdYlGn",
                aspect="auto",
                zmin=-1, zmax=1,
                text_auto=".2f",
            )
            fig_heat.update_layout(height=400)
            st.plotly_chart(fig_heat, use_container_width=True)

    # Table
    display = filtered[[c for c in [
        "id", "timestamp", "source", "ticker", "headline",
        "sentiment_score", "sentiment_label", "event_type", "impact_score",
    ] if c in filtered.columns]].reset_index(drop=True)
    st.dataframe(display, use_container_width=True, height=400)


# ============================================================================
# PAGE 3 — INDEX REBALANCER
# ============================================================================

elif page == "⚖️  Index Rebalancer":
    st.title("⚖️ Module A — Tactical Index Rebalancer")
    st.caption("Dynamically adjusts stock weights in a 20-stock mock index based on NLP sentiment.")

    rb = st.session_state.rebalancer

    if not rb.history:
        st.info("Run the pipeline first to generate rebalancing data.", icon="ℹ️")
        # Show initial weights as a baseline
        st.subheader("Initial Index Weights")
        init_df = pd.DataFrame([
            {"Ticker": t, "Name": m["name"], "Sector": m["sector"],
             "Weight": m["init_weight"]}
            for t, m in MOCK_INDEX.items()
        ])
        fig = px.bar(init_df, x="Ticker", y="Weight", color="Sector",
                     title="Initial Equal-Weighted Index",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        st.plotly_chart(fig, use_container_width=True)
        st.stop()

    # Current weights
    w_df = rb.weight_dataframe()

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📊 Current Index Weights vs. Initial")
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            name="Initial Weight",
            x=w_df["Ticker"], y=w_df["InitWeight"],
            marker_color="lightblue", opacity=0.7,
        ))
        fig_bar.add_trace(go.Bar(
            name="Current Weight",
            x=w_df["Ticker"], y=w_df["Weight"],
            marker_color=[
                "#00c851" if d > 0 else "#ff4444"
                for d in w_df["WeightChange"]
            ],
        ))
        fig_bar.update_layout(
            barmode="group", height=380,
            xaxis_title="Ticker", yaxis_title="Weight",
            yaxis_tickformat=".1%",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col2:
        st.subheader("🏆 Top Overweights")
        top_ow = w_df.nlargest(5, "WeightChange")[["Ticker", "WeightChange"]]
        top_ow["WeightChange"] = (top_ow["WeightChange"] * 100).round(2)
        top_ow.columns = ["Ticker", "Δ Weight (%)"]
        st.dataframe(top_ow, hide_index=True, use_container_width=True)

        st.subheader("📉 Top Underweights")
        top_uw = w_df.nsmallest(5, "WeightChange")[["Ticker", "WeightChange"]]
        top_uw["WeightChange"] = (top_uw["WeightChange"] * 100).round(2)
        top_uw.columns = ["Ticker", "Δ Weight (%)"]
        st.dataframe(top_uw, hide_index=True, use_container_width=True)

    # Sector breakdown
    st.subheader("🏢 Sector Weight Allocation")
    sector_w = rb.sector_weights
    init_sector: dict = {}
    for t, m in MOCK_INDEX.items():
        s = m["sector"]
        init_sector[s] = init_sector.get(s, 0.0) + m["init_weight"]

    sec_df = pd.DataFrame({
        "Sector":  list(sector_w.keys()),
        "Current": list(sector_w.values()),
        "Initial": [init_sector.get(s, 0) for s in sector_w.keys()],
    })
    fig_sector = px.bar(
        sec_df.melt(id_vars="Sector", var_name="Type", value_name="Weight"),
        x="Sector", y="Weight", color="Type", barmode="group",
        color_discrete_map={"Current": "#667eea", "Initial": "lightgray"},
        text_auto=".1%",
    )
    fig_sector.update_layout(height=350, yaxis_tickformat=".1%")
    st.plotly_chart(fig_sector, use_container_width=True)

    # Weight evolution over time
    st.subheader("📈 Weight Evolution Over Rebalancing Events")
    hist_df = rb.history_dataframe()
    if not hist_df.empty:
        # Focus on top 5 by current weight
        top_tickers = w_df.nlargest(5, "Weight")["Ticker"].tolist()
        hist_top = hist_df[hist_df["ticker"].isin(top_tickers)]
        hist_top = hist_top.sort_values("timestamp")
        fig_evo = px.line(
            hist_top, x="timestamp", y="weight",
            color="ticker", line_group="ticker",
            markers=True,
            color_discrete_sequence=px.colors.qualitative.Set1,
        )
        fig_evo.update_layout(height=380, yaxis_tickformat=".1%",
                              xaxis_title="Rebalance Event", yaxis_title="Weight")
        st.plotly_chart(fig_evo, use_container_width=True)

    # Full weight table
    with st.expander("📋 Full Weight Table"):
        display_w = w_df.copy()
        display_w["Weight"] = (display_w["Weight"] * 100).round(3)
        display_w["InitWeight"] = (display_w["InitWeight"] * 100).round(3)
        display_w["WeightChange"] = (display_w["WeightChange"] * 100).round(3)
        display_w.columns = ["Ticker", "Name", "Sector", "Weight (%)",
                             "Initial (%)", "Change (%)"]
        st.dataframe(display_w, hide_index=True, use_container_width=True)


# ============================================================================
# PAGE 4 — STRESS TESTING
# ============================================================================

elif page == "🔥 Stress Testing":
    st.title("🔥 Module B — Portfolio Stress Testing")
    st.caption("Event-driven stress simulation on a synthetic wholesale banking portfolio.")

    engine = st.session_state.stress_engine
    portfolio = engine.portfolio

    # Portfolio overview
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Portfolio NAV", f"${portfolio.total_value:.1f}M")
    with col2:
        n_assets = len(portfolio.assets)
        st.metric("# Assets", n_assets)
    with col3:
        loans_val = portfolio.by_type.get("loan", 0)
        st.metric("Loan Book", f"${loans_val:.0f}M")
    with col4:
        bond_val = portfolio.by_type.get("gov_bond", 0) + portfolio.by_type.get("corp_bond", 0)
        st.metric("Bond Book", f"${bond_val:.0f}M")

    # Manual scenario runner
    st.markdown("---")
    st.subheader("🎛️ Run a Scenario Manually")

    col_s1, col_s2 = st.columns([2, 1])
    with col_s1:
        chosen_scenario = st.selectbox(
            "Select Stress Scenario",
            list(SHOCK_SCENARIOS.keys()),
            index=0,
        )
        scenario_desc = SHOCK_SCENARIOS[chosen_scenario].get("description", "")
        st.caption(f"📝 {scenario_desc}")

    with col_s2:
        if st.button("▶️ Run Scenario", type="primary", use_container_width=True):
            with st.spinner(f"Running {chosen_scenario} stress test …"):
                result = engine.run_scenario(chosen_scenario)
                st.session_state[f"stress_result_{chosen_scenario}"] = result
            st.success(f"Completed! P&L: ${result['pnl_impact']:+.1f}M ({result['pnl_pct']:+.2f}%)")
            st.rerun()

    # Display latest result
    latest = engine.latest_result()
    if latest:
        st.markdown("---")
        st.subheader(f"📊 Latest Result: {latest['scenario']}")

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Pre-Stress NAV",  f"${latest['pre_value']:.1f}M")
        with c2:
            delta_color = "normal" if latest["pnl_impact"] >= 0 else "inverse"
            st.metric(
                "Post-Stress NAV",
                f"${latest['post_value']:.1f}M",
                delta=f"${latest['pnl_impact']:+.1f}M",
                delta_color=delta_color,
            )
        with c3:
            st.metric("P&L Impact", f"{latest['pnl_pct']:+.2f}%")

        # Shocks applied
        with st.expander("🔬 Shocks Applied"):
            shocks = latest.get("shocks_applied", {})
            shock_df = pd.DataFrame([
                {"Parameter": k.replace("_", " ").title(), "Value": v}
                for k, v in shocks.items()
            ])
            st.dataframe(shock_df, hide_index=True)

        # Asset-level breakdown
        st.subheader("📦 Asset-Level P&L Breakdown")
        asset_df = pd.DataFrame(latest.get("asset_breakdown", []))
        if not asset_df.empty:
            fig_assets = px.bar(
                asset_df.sort_values("pnl"),
                x="pnl", y="name",
                color="type",
                orientation="h",
                text="pnl",
                color_discrete_sequence=px.colors.qualitative.Set2,
            )
            fig_assets.update_traces(texttemplate="$%{text:.1f}M", textposition="outside")
            fig_assets.update_layout(height=500, xaxis_title="P&L (USD M)", yaxis_title="",
                                      showlegend=True)
            st.plotly_chart(fig_assets, use_container_width=True)

        # Before/After by asset type
        st.subheader("🔄 Portfolio Composition: Before vs. After")
        by_type_pre  = latest.get("by_type_pre",  {})
        by_type_post = latest.get("by_type_post", {})
        all_types = set(list(by_type_pre.keys()) + list(by_type_post.keys()))
        comp_df = pd.DataFrame({
            "Type":  list(all_types),
            "Pre":   [by_type_pre.get(t,  0) for t in all_types],
            "Post":  [by_type_post.get(t, 0) for t in all_types],
        })
        fig_comp = go.Figure(data=[
            go.Bar(name="Pre-Stress",  x=comp_df["Type"], y=comp_df["Pre"],  marker_color="#667eea"),
            go.Bar(name="Post-Stress", x=comp_df["Type"], y=comp_df["Post"], marker_color="#ff6b6b"),
        ])
        fig_comp.update_layout(barmode="group", height=350,
                                yaxis_title="Value (USD M)")
        st.plotly_chart(fig_comp, use_container_width=True)

    # Scenario comparison heatmap
    if len(engine.results) > 0:
        st.markdown("---")
        st.subheader("🌐 Scenario Comparison Matrix")
        summary_df = engine.summary_dataframe()
        if not summary_df.empty:
            fig_summary = px.bar(
                summary_df.sort_values("pnl_pct"),
                x="scenario", y="pnl_pct",
                color="pnl_pct",
                color_continuous_scale="RdYlGn",
                text_auto=".2f",
                labels={"pnl_pct": "P&L (%)"},
            )
            fig_summary.update_layout(height=350, showlegend=False,
                                       coloraxis_showscale=False)
            st.plotly_chart(fig_summary, use_container_width=True)

            # All stress tests table
            with st.expander("📋 All Stress Test Results"):
                st.dataframe(
                    summary_df[["timestamp", "scenario", "pre_value",
                                "post_value", "pnl_impact", "pnl_pct",
                                "trigger_impact"]].reset_index(drop=True),
                    use_container_width=True,
                )
    else:
        st.info("Run a scenario above or execute the pipeline to see stress test results.", icon="ℹ️")


# ============================================================================
# PAGE 5 — ANALYZE TEXT
# ============================================================================

elif page == "🔬 Analyze Text":
    st.title("🔬 On-Demand Text Analyzer")
    st.caption("Submit any financial text for instant NLP analysis by the Risk Engine.")

    col1, col2 = st.columns([3, 1])
    with col1:
        text_input = st.text_area(
            "Enter financial text (news headline, tweet, etc.):",
            placeholder="e.g., Apple reports record Q3 earnings; revenue beats estimates by 8%...",
            height=120,
        )
        ticker_input = st.text_input("Company Ticker (optional):", placeholder="AAPL")

    with col2:
        st.markdown("**Quick examples:**")
        examples = {
            "📈 Bullish Earnings": "Apple Inc. blows past analyst expectations with record quarterly revenue of \$94.9B, driven by strong iPhone 15 and services growth.",
            "📉 Credit Downgrade": "Moody's downgrades XOM corporate bonds to junk status amid rising leverage and deteriorating cash flows in weak oil price environment.",
            "🌍 Geopolitical": "Escalating tensions in the Middle East push crude oil past \$130/barrel, triggering emergency OPEC meeting and global market sell-off.",
            "🏦 M&A Event": "Microsoft confirms acquisition of Activision Blizzard for \$68.7B in all-cash deal, subject to regulatory clearance.",
            "📊 Rate Hike": "Federal Reserve raises interest rates by 75bps, signaling continued tightening to combat 8.5% CPI inflation amid recession fears.",
        }
        selected = st.radio("Pick example:", list(examples.keys()), label_visibility="collapsed")

    if st.button("🔍 Analyze", type="primary"):
        input_text = text_input.strip() if text_input.strip() else examples.get(selected, "")
        if not input_text:
            st.warning("Please enter text or select an example.")
        else:
            with st.spinner("Running NLP analysis …"):
                item = {
                    "source":    "Dashboard:Playground",
                    "headline":  input_text[:200],
                    "full_text": input_text,
                    "ticker":    ticker_input.upper() if ticker_input else None,
                    "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                    "uid":       "dash-" + str(hash(input_text)),
                }
                result = analyze(item)

            st.markdown("---")
            st.subheader("🎯 Analysis Results")

            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                sentiment = result["sentiment_score"]
                color = "green" if sentiment > 0.1 else ("red" if sentiment < -0.1 else "orange")
                st.markdown(f"### :{color}[Sentiment Score]")
                st.markdown(f"<h1 style='text-align:center;color:{color};'>{sentiment:+.3f}</h1>",
                            unsafe_allow_html=True)
                st.caption(f"Label: **{result['sentiment_label'].upper()}** | "
                           f"Confidence: {result.get('confidence', 0):.1%}")

            with col_r2:
                st.markdown("### 🗂️ Event Classification")
                st.info(f"**{result['event_type']}**", icon="📌")
                st.caption(f"Model confidence in classification shown above")

            with col_r3:
                st.plotly_chart(
                    make_gauge(result["impact_score"], "Impact Score"),
                    use_container_width=True,
                )

            # Full output JSON
            with st.expander("📄 Full Signal Output (JSON)"):
                display_result = {
                    k: v for k, v in result.items()
                    if k not in ("uid", "raw_metadata", "full_text")
                }
                st.json(display_result)

            # Contextual recommendation
            st.markdown("---")
            st.subheader("💡 Risk Engine Recommendation")
            impact = result["impact_score"]
            sentiment = result["sentiment_score"]
            event_type = result["event_type"]

            if impact >= 7:
                st.error(
                    f"🚨 **HIGH IMPACT EVENT DETECTED** — {event_type}\n\n"
                    f"Impact Score: **{impact:.1f}/10**. "
                    f"Recommend triggering **Module B Stress Test** immediately. "
                    f"Portfolio positions exposed to this event type should be reviewed.",
                    icon="🚨",
                )
            elif sentiment < -0.3:
                st.warning(
                    f"⚠️ **NEGATIVE SENTIMENT SIGNAL** — {event_type}\n\n"
                    f"Sentiment: **{sentiment:+.3f}**. "
                    f"Consider reducing weights for affected tickers in Module A.",
                    icon="⚠️",
                )
            elif sentiment > 0.3 and impact >= 5:
                st.success(
                    f"✅ **POSITIVE SIGNAL** — {event_type}\n\n"
                    f"Sentiment: **{sentiment:+.3f}** | Impact: **{impact:.1f}**. "
                    f"Consider increasing weights for affected tickers in Module A.",
                    icon="✅",
                )
            else:
                st.info(
                    f"ℹ️ **LOW-IMPACT SIGNAL** — {event_type}\n\n"
                    f"Impact: **{impact:.1f}/10**. No immediate action required.",
                    icon="ℹ️",
                )
