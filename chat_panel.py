"""Slide-in AI chat panel — importable from any page."""

import streamlit as st

_PANEL_CSS = """
<style>
/* ── Reposition Streamlit dialog as a right-side slide-in panel ── */
div[data-testid="stDialog"] [role="dialog"] {
    margin-left: auto !important;
    margin-right: 0 !important;
    max-width: 480px !important;
    width: 480px !important;
    height: 100vh !important;
    max-height: 100vh !important;
    border-radius: 0 !important;
    animation: delta-slide-in 0.25s ease-out !important;
}

@keyframes delta-slide-in {
    from { transform: translateX(40px); opacity: 0.5; }
    to   { transform: translateX(0);    opacity: 1;   }
}

/* ── Solid panel background — works in both dark and light mode ── */
@media (prefers-color-scheme: dark) {
    div[data-testid="stDialog"] [role="dialog"] {
        background: #0f1116 !important;
        border-left: 2px solid #23272f !important;
        color: #e4e6ea !important;
    }
}
@media (prefers-color-scheme: light) {
    div[data-testid="stDialog"] [role="dialog"] {
        background: #ffffff !important;
        border-left: 2px solid #d1d5db !important;
        color: #1f2937 !important;
    }
}
/* Streamlit also sets [data-testtheme] — cover both with fallback */
[data-testid="stAppViewContainer"][data-testtheme="dark"] ~ * div[data-testid="stDialog"] [role="dialog"],
div[data-testid="stDialog"] [role="dialog"] {
    background: #0f1116 !important;
    border-left: 2px solid #23272f !important;
}

/* Dim the backdrop */
div[data-testid="stDialog"] > div:first-child {
    background: rgba(0, 0, 0, 0.45) !important;
}

/* ── Example-question buttons ── */
div[data-testid="stDialog"] button[kind="secondary"] {
    text-align: left !important;
    font-size: 0.85rem !important;
    padding: 8px 12px !important;
    white-space: normal !important;
    line-height: 1.35 !important;
}

/* ── Input form row — make the send button match the input height ── */
div[data-testid="stDialog"] .stForm [data-testid="stFormSubmitButton"] button {
    padding-top: 0.55rem !important;
    padding-bottom: 0.55rem !important;
}
</style>
"""

_EXAMPLES = [
    "What was the single most profitable trade and why?",
    "Is the CCGT overcommitted during peak hours? Show the math",
    "Which trades are missing REMIT reports? What's the penalty exposure?",
    "Calculate the break-even electricity price for a CCGT cold start",
    "Compare wind forecast accuracy — is there a systematic bias?",
    "What was the worst imbalance event in the dataset?",
]


def _get_response(prompt: str) -> str:
    """Route prompt through the orchestrator or AgentCore and return text."""
    from agentcore_client import is_agentcore_enabled, invoke_trading_chat_agent

    if is_agentcore_enabled():
        return invoke_trading_chat_agent(prompt)

    from multi_agent import create_orchestrator

    if "orchestrator" not in st.session_state:
        st.session_state.orchestrator = create_orchestrator()

    result = st.session_state.orchestrator(prompt)
    content_blocks = result.message.get("content", [])
    text_parts = [
        block["text"]
        for block in content_blocks
        if isinstance(block, dict) and "text" in block
    ]
    return "".join(text_parts) or str(result.message)


@st.dialog("▲ DELTA AI Analyst", width="large")
def _chat_dialog():
    """Chat panel rendered inside a right-anchored Streamlit dialog."""
    from agentcore_client import is_agentcore_enabled

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    st.caption(
        "Multi-agent on **Bedrock AgentCore**"
        if is_agentcore_enabled()
        else "5 Claude agents · 1 orchestrator + 4 specialists · every answer cites source data"
    )

    # ── Input form — always visible at top ──
    with st.form("delta_chat_form", clear_on_submit=True):
        cols = st.columns([6, 1])
        user_input = cols[0].text_input(
            "Message",
            placeholder="Ask the trading desk anything…",
            label_visibility="collapsed",
        )
        submitted = cols[1].form_submit_button("↑")

    prompt = user_input if submitted and user_input else None

    # ── Scrollable message / suggestion area ──
    msg_area = st.container(height=420)

    with msg_area:
        if not st.session_state.chat_messages and not prompt:
            st.markdown("**Suggested questions:**")
            for i, ex in enumerate(_EXAMPLES):
                if st.button(ex, key=f"chat_ex_{i}", use_container_width=True):
                    prompt = ex

        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── Process prompt ──
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with msg_area:
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Routing to specialist agent…"):
                    try:
                        response_text = _get_response(prompt)
                    except Exception as e:
                        response_text = (
                            f"Error: {e}\n\nTry rephrasing your question."
                        )
                st.markdown(response_text)
        st.session_state.chat_messages.append(
            {"role": "assistant", "content": response_text}
        )

    # ── Reset ──
    if st.session_state.chat_messages:
        if st.button("Reset conversation", key="chat_reset", use_container_width=True):
            st.session_state.chat_messages.clear()
            st.session_state.pop("orchestrator", None)
            st.rerun()


def render_chat_panel():
    """Inject panel CSS and add an 'AI Chat' button to the sidebar.

    Call this once at the end of every page.
    """
    st.markdown(_PANEL_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("---")
        if st.button("💬  AI Chat", key="delta_chat_open", use_container_width=True):
            _chat_dialog()
