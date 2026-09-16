import streamlit as st
from chat_agent import create_chat_agent

st.set_page_config(page_title="AI Trading Analyst", page_icon="🤖", layout="wide")
st.title("🤖 AI Trading Analyst")
st.markdown(
    "Ask questions about the portfolio, market data, compliance, or dispatch. "
    "Every answer is grounded in the dataset with source citations."
)

if "agent" not in st.session_state:
    with st.spinner("Initializing AI agent (Claude Opus 4.6 via Bedrock)..."):
        st.session_state.agent = create_chat_agent()
    st.session_state.messages = []

st.divider()
st.markdown("**Example questions:**")
examples = [
    "What was the most profitable trading day and why?",
    "Which trades are missing REMIT reports?",
    "Calculate the break-even price for a CCGT cold start",
    "Compare wind forecast accuracy — are forecasts biased?",
    "What is the CCGT overcommitment risk during peak hours?",
    "Show the top 5 highest-priced intraday periods",
]
cols = st.columns(3)
for i, ex in enumerate(examples):
    if cols[i % 3].button(ex, key=f"ex_{i}", use_container_width=True):
        st.session_state.pending_question = ex

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask the trading analyst...")

if "pending_question" in st.session_state:
    prompt = st.session_state.pop("pending_question")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing data..."):
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
                response_text = f"Error querying agent: {str(e)}"

        st.markdown(response_text)
        st.session_state.messages.append({"role": "assistant", "content": response_text})
