"""Slide-in AI chat panel — importable from any page."""

import streamlit as st

_PANEL_CSS_BASE = """
<style>
/* ── Base dialog styling ── */
div[data-testid="stDialog"] [role="dialog"] {
    max-width: 480px !important;
    width: 480px !important;
    height: 100vh !important;
    max-height: 100vh !important;
    border-radius: 0 !important;
    transition: all 0.25s ease-out !important;
}

/* ── Solid panel background — works in both dark and light mode ── */
@media (prefers-color-scheme: dark) {
    div[data-testid="stDialog"] [role="dialog"] {
        background: #0f1116 !important;
        color: #e4e6ea !important;
    }
}
@media (prefers-color-scheme: light) {
    div[data-testid="stDialog"] [role="dialog"] {
        background: #ffffff !important;
        color: #1f2937 !important;
    }
}
[data-testid="stAppViewContainer"][data-testtheme="dark"] ~ * div[data-testid="stDialog"] [role="dialog"],
div[data-testid="stDialog"] [role="dialog"] {
    background: #0f1116 !important;
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

/* ── Position toggle buttons ── */
.chat-pos-toggle button {
    font-size: 0.7rem !important;
    padding: 2px 8px !important;
    min-height: 0 !important;
    line-height: 1.4 !important;
}
</style>
"""

_PANEL_CSS_LEFT = """
<style>
div[data-testid="stDialog"] [role="dialog"] {
    margin-left: 0 !important;
    margin-right: auto !important;
    border-right: 2px solid #23272f !important;
    border-left: none !important;
    animation: delta-slide-left 0.25s ease-out !important;
}
@keyframes delta-slide-left {
    from { transform: translateX(-40px); opacity: 0.5; }
    to   { transform: translateX(0);     opacity: 1;   }
}
@media (prefers-color-scheme: light) {
    div[data-testid="stDialog"] [role="dialog"] {
        border-right: 2px solid #d1d5db !important;
    }
}
</style>
"""

_PANEL_CSS_RIGHT = """
<style>
div[data-testid="stDialog"] [role="dialog"] {
    margin-left: auto !important;
    margin-right: 0 !important;
    border-left: 2px solid #23272f !important;
    border-right: none !important;
    animation: delta-slide-right 0.25s ease-out !important;
}
@keyframes delta-slide-right {
    from { transform: translateX(40px); opacity: 0.5; }
    to   { transform: translateX(0);    opacity: 1;   }
}
@media (prefers-color-scheme: light) {
    div[data-testid="stDialog"] [role="dialog"] {
        border-left: 2px solid #d1d5db !important;
    }
}
</style>
"""

_PANEL_CSS_FLOAT = """
<style>
div[data-testid="stDialog"] [role="dialog"] {
    margin: 2vh auto !important;
    height: 85vh !important;
    max-height: 85vh !important;
    border-radius: 16px !important;
    border: 1px solid #23272f !important;
    box-shadow: 0 24px 48px rgba(0, 0, 0, 0.4) !important;
    animation: delta-float-in 0.25s ease-out !important;
}
@keyframes delta-float-in {
    from { transform: scale(0.95); opacity: 0.5; }
    to   { transform: scale(1);    opacity: 1;   }
}
@media (prefers-color-scheme: light) {
    div[data-testid="stDialog"] [role="dialog"] {
        border: 1px solid #d1d5db !important;
        box-shadow: 0 24px 48px rgba(0, 0, 0, 0.15) !important;
    }
}
</style>
"""

_POSITION_CSS = {
    "◧ Left": _PANEL_CSS_LEFT,
    "◈ Float": _PANEL_CSS_FLOAT,
    "◨ Right": _PANEL_CSS_RIGHT,
}

_EXAMPLES = [
    "What was the single most profitable trade and why?",
    "Is the CCGT overcommitted during peak hours? Show the math",
    "Which trades are missing REMIT reports? What's the penalty exposure?",
    "Calculate the break-even electricity price for a CCGT cold start",
    "Compare wind forecast accuracy — is there a systematic bias?",
    "What was the worst imbalance event in the dataset?",
]


def _get_response(prompt: str) -> str:
    """Invoke the multi-agent orchestrator on AgentCore and return text."""
    from agentcore_client import invoke_trading_chat_agent

    session_id = st.session_state.get("agentcore_session_id")
    if not session_id:
        import uuid
        session_id = str(uuid.uuid4())
        st.session_state.agentcore_session_id = session_id

    return invoke_trading_chat_agent(prompt, session_id=session_id)


@st.dialog("▲ DELTA AI Analyst", width="large")
def _chat_dialog():
    """Chat panel rendered inside a Streamlit dialog with position toggle."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_position" not in st.session_state:
        st.session_state.chat_position = "◨ Right"

    pos_cols = st.columns([4, 1, 1, 1])
    pos_cols[0].caption("Multi-agent orchestrator on **Bedrock AgentCore**")
    for i, pos in enumerate(["◧ Left", "◈ Float", "◨ Right"]):
        is_active = st.session_state.chat_position == pos
        if pos_cols[i + 1].button(
            pos,
            key=f"chat_pos_{pos}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.chat_position = pos
            st.rerun()

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
            st.session_state.pop("agentcore_session_id", None)
            st.rerun()


def render_chat_panel():
    """Inject panel CSS and add an 'AI Chat' button to the sidebar.

    Call this once at the end of every page.
    """
    st.markdown(_PANEL_CSS_BASE, unsafe_allow_html=True)
    pos = st.session_state.get("chat_position", "◨ Right")
    st.markdown(_POSITION_CSS.get(pos, _PANEL_CSS_RIGHT), unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("---")
        if st.button("💬  AI Chat", key="delta_chat_open", use_container_width=True):
            _chat_dialog()
