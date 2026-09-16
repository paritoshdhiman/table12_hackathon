import streamlit as st
from data_loader import extract_data_if_needed

st.set_page_config(
    page_title="Energy Trading Optimizer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

extract_data_if_needed()

st.title("⚡ Intraday Energy Trading Optimizer")
st.markdown("**DE-LU Bidding Zone | EPEX SPOT | 90-Day Analysis (Jan–Apr 2026)**")
st.info("Select a page from the sidebar to explore the portfolio, market data, dispatch optimization, scenarios, compliance, or chat with the AI analyst.")
