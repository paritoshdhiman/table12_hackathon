import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from data_loader import (
    load_trade_blotter, load_remit_transactions, load_contract_obligations,
    load_imbalance_prices,
)
from compliance import check_remit_compliance, check_contract_obligations, analyze_imbalance_exposure

st.set_page_config(page_title="Compliance & Risk", page_icon="🛡️", layout="wide")
st.title("🛡️ Compliance & Risk Monitor")

trades = load_trade_blotter()
remit = load_remit_transactions()
contracts = load_contract_obligations()
imbalance = load_imbalance_prices()

tab1, tab2, tab3 = st.tabs(["REMIT Compliance", "Contract Obligations", "Imbalance Exposure"])

# ── Tab 1: REMIT ─────────────────────────────────────────────────────────────
with tab1:
    st.header("REMIT II Transaction Reporting")
    rc = check_remit_compliance(trades, remit)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Compliance Rate", f"{rc['compliance_rate']:.1f}%")
    m2.metric("Missing Reports", f"{rc['missing_count']}")
    m3.metric("Rejected", f"{len(rc['rejected_reports'])}")
    m4.metric("Pending", f"{len(rc['pending_reports'])}")

    col_l, col_r = st.columns(2)
    with col_l:
        status_df = pd.DataFrame(
            list(rc["status_counts"].items()), columns=["Status", "Count"]
        )
        fig = px.pie(
            status_df, values="Count", names="Status",
            title="REMIT Report Status Distribution",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Reporting Summary")
        st.markdown(f"""
        - **Total trades:** {rc['total_trades']} (trade_blotter.csv)
        - **REMIT reports filed:** {rc['total_remit_reports']} (remit_transactions.csv)
        - **Trades without REMIT report:** **{rc['missing_count']}** — these trades have no
          corresponding record in remit_transactions.csv
        - **Accepted:** {rc['status_counts'].get('ACCEPTED', 0)}
        - **Submitted (pending acceptance):** {rc['status_counts'].get('SUBMITTED', 0)}
        - **Pending:** {rc['status_counts'].get('PENDING', 0)}
        - **Rejected:** {rc['status_counts'].get('REJECTED', 0)}

        *REMIT II requires all wholesale energy transactions to be reported to ACER within T+1
        business day. Penalties: up to €500K per violation.*
        """)

    if not rc["rejected_reports"].empty:
        st.subheader("Rejected REMIT Reports")
        st.dataframe(
            rc["rejected_reports"][["report_id", "trade_id", "submission_timestamp",
                                    "reporting_deadline", "status", "rejection_reason"]],
            use_container_width=True, hide_index=True,
        )
        st.caption("Source: remit_transactions.csv, status='REJECTED'")

    with st.expander(f"Trades Missing REMIT Reports ({rc['missing_count']} trades)"):
        missing_trades = trades[trades["trade_id"].isin(rc["missing_reports"])]
        st.dataframe(
            missing_trades[["trade_id", "timestamp_executed", "direction",
                            "volume_mw", "price_eur_mwh", "strategy"]].head(50),
            use_container_width=True, hide_index=True,
        )
        if rc["missing_count"] > 50:
            st.caption(f"Showing first 50 of {rc['missing_count']} unreported trades")
        st.caption("Source: trade_blotter.csv trade_ids not found in remit_transactions.csv")

# ── Tab 2: Contract Obligations ──────────────────────────────────────────────
with tab2:
    st.header("Contract Obligation Fulfillment")
    obligations = check_contract_obligations(contracts, trades)

    for _, row in obligations.iterrows():
        status_icon = "✅" if row["within_tolerance"] else "❌"
        cols = st.columns([3, 2, 2, 2, 1])
        cols[0].markdown(f"**{row['contract_id']}** — {row['counterparty']}")
        cols[1].metric("Committed", f"{row['committed_mwh']:,.0f} MWh")
        cols[2].metric("Delivered", f"{row['delivered_mwh']:,.0f} MWh")
        cols[3].metric("Deviation", f"{row['deviation_pct']:+.1f}%",
                       delta=f"Tolerance: ±{row['tolerance_pct']}%")
        cols[4].markdown(f"### {status_icon}")
        if not row["within_tolerance"]:
            st.error(
                f"⚠️ {row['contract_id']}: deviation {row['deviation_pct']:+.1f}% "
                f"exceeds ±{row['tolerance_pct']}% tolerance. "
                f"Penalty exposure: **€{row['penalty_exposure_eur']:,.0f}**"
            )
        st.divider()

    fig_ob = go.Figure()
    fig_ob.add_trace(go.Bar(
        x=obligations["contract_id"], y=obligations["committed_mwh"],
        name="Committed", marker_color="#636EFA",
    ))
    fig_ob.add_trace(go.Bar(
        x=obligations["contract_id"], y=obligations["delivered_mwh"],
        name="Delivered", marker_color="#00CC96",
    ))
    fig_ob.update_layout(
        title="Committed vs Delivered Volume",
        barmode="group", yaxis_title="MWh",
    )
    st.plotly_chart(fig_ob, use_container_width=True)
    st.caption("Source: contract_obligations.csv + trade_blotter.csv (SELL trades matched by plant_id)")

    total_penalty = obligations["penalty_exposure_eur"].sum()
    if total_penalty > 0:
        st.warning(f"Total penalty exposure across all contracts: **€{total_penalty:,.0f}**")

# ── Tab 3: Imbalance Exposure ────────────────────────────────────────────────
with tab3:
    st.header("Imbalance Settlement Analysis")
    imb = analyze_imbalance_exposure(imbalance)

    m1, m2, m3 = st.columns(3)
    m1.metric("Avg Long Price", f"€{imb['avg_long_price']:.2f}/MWh")
    m2.metric("Avg Short Price", f"€{imb['avg_short_price']:.2f}/MWh")
    m3.metric("Avg Spread (Short−Long)", f"€{imb['avg_spread']:.2f}/MWh")

    col_l, col_r = st.columns(2)
    with col_l:
        state_df = pd.DataFrame(
            list(imb["state_counts"].items()), columns=["State", "Count"]
        )
        fig_state = px.pie(
            state_df, values="Count", names="State",
            title="System Regulation State Distribution",
            color_discrete_map={"SHORT": "#EF553B", "LONG": "#636EFA", "BALANCED": "#00CC96"},
        )
        st.plotly_chart(fig_state, use_container_width=True)

    with col_r:
        imbalance["spread"] = (
            imbalance["imbalance_price_short_eur_mwh"] -
            imbalance["imbalance_price_long_eur_mwh"]
        )
        fig_spread = px.histogram(
            imbalance, x="spread", nbins=60,
            title="Imbalance Price Spread Distribution (Short − Long)",
            labels={"spread": "Spread (€/MWh)"},
            color_discrete_sequence=["#AB63FA"],
        )
        st.plotly_chart(fig_spread, use_container_width=True)

    st.subheader("Top 10 Worst Imbalance Events")
    st.dataframe(imb["worst_events"], use_container_width=True, hide_index=True)
    st.caption("Source: imbalance_prices.csv — ranked by short-long price spread")

    st.subheader("Imbalance Prices Over Time")
    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(
        x=imbalance["timestamp_utc"], y=imbalance["imbalance_price_short_eur_mwh"],
        name="Short Price", line=dict(color="#EF553B", width=0.8),
    ))
    fig_ts.add_trace(go.Scatter(
        x=imbalance["timestamp_utc"], y=imbalance["imbalance_price_long_eur_mwh"],
        name="Long Price", line=dict(color="#636EFA", width=0.8),
    ))
    fig_ts.update_layout(
        title="Imbalance Settlement Prices",
        yaxis_title="€/MWh", height=400,
    )
    st.plotly_chart(fig_ts, use_container_width=True)
    st.caption("Source: imbalance_prices.csv (8,640 quarter-hourly periods)")
