"""Client for invoking agents deployed on Amazon Bedrock AgentCore.

Provides both a streaming wrapper (for the Strands TradingChatAgent) and a
simple request/response wrapper (for the MarketAnalystAgent).  Falls back to
local agent execution when no AgentCore ARN is configured, so the Streamlit
app works in both local-dev and deployed modes.
"""

import json
import os
import uuid

import boto3

AGENTCORE_REGION = os.environ.get("AGENTCORE_REGION", "us-east-1")

TRADING_CHAT_AGENT_ARN = os.environ.get("TRADING_CHAT_AGENT_ARN", "")
MARKET_ANALYST_AGENT_ARN = os.environ.get("MARKET_ANALYST_AGENT_ARN", "")


def _get_client():
    return boto3.client(
        "bedrock-agent-runtime",
        region_name=AGENTCORE_REGION,
    )


def is_agentcore_enabled() -> bool:
    """True when at least one agent ARN is configured via env vars."""
    return bool(TRADING_CHAT_AGENT_ARN or MARKET_ANALYST_AGENT_ARN)


def invoke_trading_chat_agent(prompt: str, session_id: str | None = None) -> str:
    """Invoke the TradingChatAgent on AgentCore and return the text response.

    Uses the AgentCore InvokeAgentRuntime API with streaming response handling.
    """
    if not TRADING_CHAT_AGENT_ARN:
        raise RuntimeError(
            "TRADING_CHAT_AGENT_ARN not set — configure the env var "
            "with the deployed agent ARN to use AgentCore."
        )

    client = _get_client()
    session_id = session_id or str(uuid.uuid4())

    response = client.invoke_agent_runtime(
        agentRuntimeArn=TRADING_CHAT_AGENT_ARN,
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
        qualifier="DEFAULT",
    )

    chunks = []
    for event in response.get("response", {}).get("PayloadPart", []):
        chunk = event.get("bytes", b"")
        if chunk:
            chunks.append(chunk.decode("utf-8"))

    return "".join(chunks)


def invoke_market_analyst_agent(prompt: str) -> str:
    """Invoke the MarketAnalystAgent on AgentCore and return the text response."""
    if not MARKET_ANALYST_AGENT_ARN:
        raise RuntimeError(
            "MARKET_ANALYST_AGENT_ARN not set — configure the env var "
            "with the deployed agent ARN to use AgentCore."
        )

    client = _get_client()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=MARKET_ANALYST_AGENT_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps({"prompt": prompt}).encode("utf-8"),
        qualifier="DEFAULT",
    )

    chunks = []
    for event in response.get("response", {}).get("PayloadPart", []):
        chunk = event.get("bytes", b"")
        if chunk:
            chunks.append(chunk.decode("utf-8"))

    raw = "".join(chunks)
    try:
        data = json.loads(raw)
        return data.get("response", raw)
    except (json.JSONDecodeError, TypeError):
        return raw
