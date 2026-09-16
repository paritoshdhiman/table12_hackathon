import streamlit as st
from agentcore_client import invoke_trading_chat_agent

st.set_page_config(page_title="DELTA AI Analyst", page_icon="▲", layout="wide")

try:
    from chart_theme import apply_sidebar_branding
    apply_sidebar_branding()
except Exception:
    pass

st.markdown("""
<style>
    .agent-route {
        background: #1C1C1C;
        border: 1px solid #2A2A2A;
        border-radius: 8px;
        padding: 10px 14px;
        margin: 4px 0;
        font-size: 0.85rem;
        color: #9CA3AF;
    }
    .agent-route.active { border-color: #DC262644; color: #FAFAFA; }
    .specialist-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        margin-right: 4px;
    }
    .tag-market { background: #DC262622; color: #DC2626; }
    .tag-dispatch { background: #9CA3AF22; color: #9CA3AF; }
    .tag-compliance { background: #F59E0B22; color: #F59E0B; }
    .tag-risk { background: #EF444422; color: #EF4444; }
</style>
""", unsafe_allow_html=True)

st.title("▲ DELTA AI Analyst")
st.caption("Multi-agent orchestrator on **Amazon Bedrock AgentCore** — routes queries to 4 specialist agents")

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### AWS Credentials")
    st.caption("Enter your AWS credentials to invoke agents on Bedrock AgentCore.")

    aws_region = st.text_input(
        "AWS Region",
        value=st.session_state.get("aws_region", "us-east-1"),
        key="aws_region_input",
    )
    aws_access_key = st.text_input(
        "AWS Access Key ID",
        value=st.session_state.get("aws_access_key", ""),
        key="aws_access_key_input",
    )
    aws_secret_key = st.text_input(
        "AWS Secret Access Key",
        value=st.session_state.get("aws_secret_key", ""),
        type="password",
        key="aws_secret_key_input",
    )
    aws_session_token = st.text_input(
        "AWS Session Token",
        value=st.session_state.get("aws_session_token", ""),
        type="password",
        key="aws_session_token_input",
    )

    if st.button("Save Credentials", use_container_width=True, type="primary"):
        st.session_state.aws_region = aws_region
        st.session_state.aws_access_key = aws_access_key
        st.session_state.aws_secret_key = aws_secret_key
        st.session_state.aws_session_token = aws_session_token
        st.success("Credentials saved for this session.")

    _creds_ready = bool(
        st.session_state.get("aws_access_key")
        and st.session_state.get("aws_secret_key")
    )

    if _creds_ready:
        st.markdown('<span style="color:#22c55e; font-weight:600;">Connected</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:#9CA3AF;">Not configured</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### Multi-Agent System")

    st.markdown("""
    <div class="agent-route active">
        <strong>Orchestrator</strong><br>
        Routes queries to the right specialist
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Specialist Agents:**")

    st.markdown("""
    <div class="agent-route">
        <span class="specialist-tag tag-market">MARKET</span>
        <strong>Market Analyst</strong><br>
        Prices, spreads, fuel trends, renewables
    </div>
    <div class="agent-route">
        <span class="specialist-tag tag-dispatch">DISPATCH</span>
        <strong>Dispatch Optimizer</strong><br>
        SRMC, merit-order, start-up costs, ramps
    </div>
    <div class="agent-route">
        <span class="specialist-tag tag-compliance">COMPLIANCE</span>
        <strong>Compliance Officer</strong><br>
        REMIT reports, contract tolerances, penalties
    </div>
    <div class="agent-route">
        <span class="specialist-tag tag-risk">RISK</span>
        <strong>Risk Manager</strong><br>
        P&L, imbalance, strategy performance
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### How it works")
    st.markdown("""
1. Your question goes to the **Orchestrator**
2. It routes to the best **Specialist Agent**
3. The specialist calls its **data tools**
4. Results flow back with **source citations**

Each agent is a separate Claude Opus 4.6
instance on Amazon Bedrock AgentCore with
its own system prompt and tool set.
""")

    st.markdown("---")
    st.markdown("### Grounding Policy")
    st.markdown("""
Every answer must cite:
- **Source file** (e.g., trade_blotter.csv)
- **Row number** (e.g., row 1542)
- **Formula** when computing derived values

If data doesn't support a claim, the agent says so.
""")

    if st.button("Reset Conversation", use_container_width=True):
        st.session_state.pop("messages", None)
        st.session_state.pop("agentcore_session_id", None)
        st.rerun()

# ── Check credentials ───────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

if not _creds_ready:
    st.info(
        "**Enter your AWS credentials** in the sidebar to connect to AgentCore.\n\n"
        "You need:\n"
        "- **AWS Access Key ID**\n"
        "- **AWS Secret Access Key**\n"
        "- **AWS Session Token** (if using temporary credentials)\n\n"
        "These are used only for this browser session and are never stored on disk."
    )
    st.stop()

# ── Example Questions ────────────────────────────────────────────────────────
st.markdown("#### Example questions")
col1, col2 = st.columns(2)

examples_left = [
    ("What was the single most profitable trade and why?", "risk"),
    ("Calculate the break-even electricity price for a CCGT cold start", "dispatch"),
    ("Which trades are missing REMIT reports? What's the penalty exposure?", "compliance"),
]
examples_right = [
    ("Is the CCGT overcommitted during peak hours? Show the math", "dispatch"),
    ("Compare wind forecast accuracy — is there a systematic bias?", "market"),
    ("What was the worst imbalance event in the dataset?", "risk"),
]

for ex, tag in examples_left:
    if col1.button(ex, key=f"ex_l_{ex[:20]}", use_container_width=True):
        st.session_state.pending_question = ex

for ex, tag in examples_right:
    if col2.button(ex, key=f"ex_r_{ex[:20]}", use_container_width=True):
        st.session_state.pending_question = ex

st.markdown("---")

# ── Chat History ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Chat Input ───────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask the trading desk anything about the portfolio...")

if "pending_question" in st.session_state:
    prompt = st.session_state.pop("pending_question")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        status = st.empty()
        status.markdown("*Invoking AgentCore orchestrator...*")

        try:
            if "agentcore_session_id" not in st.session_state:
                import uuid
                st.session_state.agentcore_session_id = str(uuid.uuid4())

            response_text = invoke_trading_chat_agent(
                prompt,
                session_id=st.session_state.agentcore_session_id,
                aws_access_key_id=st.session_state.get("aws_access_key"),
                aws_secret_access_key=st.session_state.get("aws_secret_key"),
                aws_session_token=st.session_state.get("aws_session_token"),
            )
        except Exception as e:
            response_text = f"Error: {str(e)}\n\nCheck your AWS credentials in the sidebar and try again."

        status.empty()
        st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})
