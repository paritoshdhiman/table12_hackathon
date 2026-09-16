import streamlit as st
import time
from multi_agent import create_orchestrator
from agentcore_client import is_agentcore_enabled, invoke_trading_chat_agent

st.set_page_config(page_title="DELTA AI Analyst", page_icon="▲", layout="wide")

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
_agentcore_mode = is_agentcore_enabled()
st.caption(
    "Multi-agent orchestrator on **Bedrock AgentCore**" if _agentcore_mode
    else "Multi-agent orchestrator — routes queries to 4 specialist agents, each with dedicated tools"
)

# ── Agent Architecture Sidebar ───────────────────────────────────────────────
with st.sidebar:
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
instance on Amazon Bedrock with its own
system prompt and tool set.
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
        st.session_state.pop("orchestrator", None)
        st.session_state.pop("messages", None)
        st.rerun()

# ── Initialize Orchestrator ──────────────────────────────────────────────────
_bedrock_available = True
if "orchestrator" not in st.session_state and not _agentcore_mode:
    try:
        with st.spinner("Initializing multi-agent orchestrator (1 orchestrator + 4 specialists)..."):
            st.session_state.orchestrator = create_orchestrator()
    except Exception as e:
        _bedrock_available = False
        st.session_state.pop("orchestrator", None)

if "messages" not in st.session_state:
    st.session_state.messages = []

if not _bedrock_available and not _agentcore_mode:
    st.warning(
        "**AWS Bedrock credentials not configured.** "
        "The AI Chat feature requires AWS credentials with access to Amazon Bedrock.\n\n"
        "To enable this feature:\n"
        "1. Configure AWS credentials: `aws configure` or set `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`\n"
        "2. Enable model access for `us.anthropic.claude-opus-4-6-v1` in the "
        "[Bedrock console](https://console.aws.amazon.com/bedrock/) (us-east-1)\n"
        "3. Reload this page\n\n"
        "All other pages (Daily Briefing, Portfolio, Market Analysis, Dispatch, Scenarios, Compliance) "
        "work without AWS credentials."
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
        status.markdown("*Orchestrator routing to specialist agent...*")

        try:
            if _agentcore_mode:
                response_text = invoke_trading_chat_agent(prompt)
            else:
                result = st.session_state.orchestrator(prompt)
                content_blocks = result.message.get("content", [])
                response_text = ""
                for block in content_blocks:
                    if isinstance(block, dict) and "text" in block:
                        response_text += block["text"]
                if not response_text:
                    response_text = str(result.message)
        except Exception as e:
            response_text = f"Error: {str(e)}\n\nTry rephrasing your question or resetting the conversation."

        status.empty()
        st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})
