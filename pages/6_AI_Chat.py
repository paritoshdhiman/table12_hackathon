import streamlit as st
import time
from chat_agent import create_chat_agent

st.set_page_config(page_title="AI Trading Analyst", page_icon="🤖", layout="wide")

st.markdown("""
<style>
    .agent-route {
        background: linear-gradient(135deg, #1a1f2e 0%, #252b3b 100%);
        border: 1px solid #2a3040;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        font-size: 0.85rem;
        color: #8892a0;
    }
    .agent-route.active { border-left: 3px solid #00D4AA; color: #FAFAFA; }
    .tool-call {
        background: #0E1117;
        border: 1px solid #00D4AA33;
        border-radius: 6px;
        padding: 8px 12px;
        font-family: monospace;
        font-size: 0.8rem;
        color: #00D4AA;
        margin: 4px 0;
    }
</style>
""", unsafe_allow_html=True)

st.title("🤖 AI Trading Analyst")
st.markdown(
    "*Claude Opus 4.6 via Amazon Bedrock — multi-tool agent with grounded data access*"
)

# ── Agent Architecture Sidebar ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Agent Architecture")
    st.markdown("""
    <div class="agent-route active">
        🧠 <strong>Orchestrator</strong><br>
        Routes queries to specialized tools
    </div>
    <div class="agent-route">
        📊 <strong>Market Data</strong><br>
        query_intraday_prices, query_fuel_prices
    </div>
    <div class="agent-route">
        🏭 <strong>Plant Operations</strong><br>
        query_plant_info, compute_marginal_cost
    </div>
    <div class="agent-route">
        📋 <strong>Trading & P&L</strong><br>
        query_trade_blotter
    </div>
    <div class="agent-route">
        🛡️ <strong>Compliance</strong><br>
        query_remit_status, query_contract_obligations
    </div>
    <div class="agent-route">
        ⚠️ <strong>Risk & Imbalance</strong><br>
        query_imbalance_data
    </div>
    <div class="agent-route">
        🌱 <strong>Renewables</strong><br>
        query_renewable_forecast
    </div>
    <div class="agent-route">
        📖 <strong>Domain Knowledge</strong><br>
        search_reference_docs (4 docs)
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Grounding Policy")
    st.markdown("""
    Every answer must cite:
    - **Source file** (e.g., trade_blotter.csv)
    - **Row number** (e.g., row 1542)
    - **Formula used** (e.g., SRMC = Gas/Eff + CO2*CI + VOM)

    If data doesn't support a claim, the agent says so.
    """)

    if st.button("🔄 Reset Conversation", use_container_width=True):
        st.session_state.pop("agent", None)
        st.session_state.pop("messages", None)
        st.rerun()

# ── Initialize Agent ─────────────────────────────────────────────────────────
if "agent" not in st.session_state:
    with st.spinner("Initializing Claude Opus 4.6 agent with 10 data tools..."):
        st.session_state.agent = create_chat_agent()
    st.session_state.messages = []

# ── Example Questions ────────────────────────────────────────────────────────
st.markdown("#### Try these questions:")
col1, col2 = st.columns(2)

examples_left = [
    "What was the single most profitable trade and why?",
    "Calculate the break-even electricity price for a CCGT cold start today",
    "Which trades are missing REMIT reports? What's the penalty exposure?",
]
examples_right = [
    "Is the CCGT overcommitted during peak hours? Show the math",
    "Compare wind forecast accuracy — is there a systematic bias?",
    "What was the worst imbalance event in the dataset?",
]

for ex in examples_left:
    if col1.button(ex, key=f"ex_l_{ex[:20]}", use_container_width=True):
        st.session_state.pending_question = ex

for ex in examples_right:
    if col2.button(ex, key=f"ex_r_{ex[:20]}", use_container_width=True):
        st.session_state.pending_question = ex

st.markdown("---")

# ── Chat History ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

# ── Chat Input ───────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask the AI analyst anything about the portfolio...")

if "pending_question" in st.session_state:
    prompt = st.session_state.pop("pending_question")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        status_placeholder = st.empty()
        status_placeholder.markdown("*🔍 Routing query to specialized tools...*")

        try:
            result = st.session_state.agent(prompt)
            content_blocks = result.message.get("content", [])
            response_text = ""
            for block in content_blocks:
                if isinstance(block, dict) and "text" in block:
                    response_text += block["text"]
            if not response_text:
                response_text = str(result.message)
        except Exception as e:
            response_text = f"⚠️ Error: {str(e)}\n\nTry rephrasing your question or resetting the conversation."

        status_placeholder.empty()
        st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})
