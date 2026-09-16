import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from data_loader import (
    load_trade_blotter, load_remit_transactions, load_contract_obligations,
    load_imbalance_prices, load_intraday_prices,
)
from compliance import check_remit_compliance, check_contract_obligations, analyze_imbalance_exposure
from chart_theme import apply_dark_theme

st.set_page_config(page_title="Compliance & Risk", page_icon="🛡️", layout="wide")
st.title("Compliance & Risk Monitor")

trades = load_trade_blotter()
remit = load_remit_transactions()
contracts = load_contract_obligations()
imbalance = load_imbalance_prices()

tab1, tab2, tab3, tab4 = st.tabs(["REMIT Compliance", "Contract Obligations", "Imbalance Exposure", "Value-at-Risk"])

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
            color_discrete_sequence=["#00D4AA", "#636EFA", "#FFB02E", "#FF4B4B"],
        )
        apply_dark_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Reporting Summary")
        st.markdown(f"""
        - **Total trades:** {rc['total_trades']} (trade_blotter.csv)
        - **REMIT reports filed:** {rc['total_remit_reports']} (remit_transactions.csv)
        - **Trades without REMIT report:** **{rc['missing_count']}**
        - **Accepted:** {rc['status_counts'].get('ACCEPTED', 0)}
        - **Submitted (pending acceptance):** {rc['status_counts'].get('SUBMITTED', 0)}
        - **Pending:** {rc['status_counts'].get('PENDING', 0)}
        - **Rejected:** {rc['status_counts'].get('REJECTED', 0)}

        *REMIT II requires all wholesale energy transactions reported to ACER within T+1 business day.
        Penalties: up to €500K per violation or 10x profit gained.*
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
        name="Delivered", marker_color="#00D4AA",
    ))
    fig_ob.update_layout(
        title="Committed vs Delivered Volume",
        barmode="group", yaxis_title="MWh",
    )
    apply_dark_theme(fig_ob)
    st.plotly_chart(fig_ob, use_container_width=True)
    st.caption("Source: contract_obligations.csv + trade_blotter.csv (SELL trades matched by plant_id)")

    total_penalty = obligations["penalty_exposure_eur"].sum()
    if total_penalty > 0:
        st.warning(f"Total penalty exposure across all contracts: **€{total_penalty:,.0f}**")

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
            color_discrete_map={"SHORT": "#EF553B", "LONG": "#636EFA", "BALANCED": "#00D4AA"},
        )
        apply_dark_theme(fig_state)
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
        apply_dark_theme(fig_spread)
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
    apply_dark_theme(fig_ts)
    st.plotly_chart(fig_ts, use_container_width=True)
    st.caption("Source: imbalance_prices.csv (8,640 quarter-hourly periods)")

with tab4:
    st.header("Portfolio Value-at-Risk (Historical Simulation)")

    intraday = load_intraday_prices()
    daily_pnl = trades.groupby("delivery_date")["pnl_eur"].sum().sort_index()

    m1, m2, m3, m4 = st.columns(4)
    var_95 = np.percentile(daily_pnl, 5)
    var_99 = np.percentile(daily_pnl, 1)
    cvar_95 = daily_pnl[daily_pnl <= var_95].mean()
    max_loss = daily_pnl.min()

    m1.metric("VaR 95%", f"€{var_95:,.0f}", help="5th percentile of daily P&L")
    m2.metric("VaR 99%", f"€{var_99:,.0f}", help="1st percentile of daily P&L")
    m3.metric("CVaR 95%", f"€{cvar_95:,.0f}", help="Expected loss beyond VaR 95%")
    m4.metric("Worst Day", f"€{max_loss:,.0f}")

    col_l, col_r = st.columns(2)
    with col_l:
        fig_var = go.Figure()
        fig_var.add_trace(go.Histogram(
            x=daily_pnl.values, nbinsx=40, name="Daily P&L",
            marker_color="#636EFA", opacity=0.7,
        ))
        fig_var.add_vline(x=var_95, line_dash="dash", line_color="#FFB02E",
                          annotation_text=f"VaR 95% = €{var_95:,.0f}")
        fig_var.add_vline(x=var_99, line_dash="dash", line_color="#FF4B4B",
                          annotation_text=f"VaR 99% = €{var_99:,.0f}")
        fig_var.add_vline(x=0, line_color="white", line_width=0.5)
        fig_var.update_layout(
            title="Daily P&L Distribution with VaR Thresholds",
            xaxis_title="Daily P&L (€)", yaxis_title="Frequency",
            height=400,
        )
        apply_dark_theme(fig_var)
        st.plotly_chart(fig_var, use_container_width=True)

    with col_r:
        cumulative = daily_pnl.cumsum()
        running_max = cumulative.cummax()
        drawdown = cumulative - running_max

        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(
            x=cumulative.index, y=cumulative.values,
            name="Cumulative P&L", line=dict(color="#00D4AA", width=2),
        ))
        fig_dd.add_trace(go.Scatter(
            x=drawdown.index, y=drawdown.values,
            name="Drawdown", fill="tozeroy",
            fillcolor="rgba(255, 75, 75, 0.2)",
            line=dict(color="#FF4B4B", width=1),
        ))
        fig_dd.update_layout(
            title="Cumulative P&L and Drawdown",
            yaxis_title="€", height=400,
        )
        apply_dark_theme(fig_dd)
        st.plotly_chart(fig_dd, use_container_width=True)

    st.subheader("Rolling 7-Day VaR")
    rolling_var = daily_pnl.rolling(7).apply(lambda x: np.percentile(x, 5), raw=True)
    fig_rvar = go.Figure()
    fig_rvar.add_trace(go.Scatter(
        x=rolling_var.index, y=rolling_var.values,
        name="Rolling 7d VaR 95%", line=dict(color="#FFB02E", width=2),
        fill="tozeroy", fillcolor="rgba(255, 176, 46, 0.1)",
    ))
    fig_rvar.add_trace(go.Scatter(
        x=daily_pnl.index, y=daily_pnl.values,
        name="Daily P&L", mode="markers",
        marker=dict(
            color=["#FF4B4B" if v < rolling_var.get(d, 0) else "#00D4AA"
                   for d, v in zip(daily_pnl.index, daily_pnl.values)],
            size=5,
        ),
    ))
    fig_rvar.update_layout(
        title="Daily P&L vs Rolling 7-Day VaR Limit",
        yaxis_title="€", height=400,
    )
    apply_dark_theme(fig_rvar)
    st.plotly_chart(fig_rvar, use_container_width=True)

    breaches = sum(1 for d, v in zip(daily_pnl.index, daily_pnl.values)
                   if v < rolling_var.get(d, 0) and pd.notna(rolling_var.get(d)))
    st.info(f"**VaR breach days:** {breaches} out of {len(daily_pnl)} trading days "
            f"({breaches/len(daily_pnl)*100:.1f}%) — "
            f"{'within expected 5% at 95% confidence' if breaches/len(daily_pnl) < 0.08 else 'elevated — risk model may need recalibration'}")
    st.caption("Source: trade_blotter.csv (daily P&L aggregation) | Method: Historical simulation VaR")
