"""Client for invoking agents deployed on Amazon Bedrock AgentCore.

Uses the InvokeAgentRuntime API per:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-invoke-agent.html
"""

import json
import uuid

import boto3

TRADING_CHAT_AGENT_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:796973510898:"
    "runtime/EnergyTrading_TradingChatAgent-27ga7MDt53"
)
MARKET_ANALYST_AGENT_ARN = (
    "arn:aws:bedrock-agentcore:us-east-1:796973510898:"
    "runtime/EnergyTrading_MarketAnalystAgent-tfd5L38JCu"
)


def _get_client(
    region: str = "us-east-1",
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
):
    kwargs = {"region_name": region}
    if aws_access_key_id and aws_secret_access_key:
        kwargs["aws_access_key_id"] = aws_access_key_id
        kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            kwargs["aws_session_token"] = aws_session_token
    return boto3.client("bedrock-agentcore", **kwargs)


def is_agentcore_enabled() -> bool:
    """Always enabled — agents are deployed and the instance role has access."""
    return True


def _parse_sse_response(response) -> str:
    """Parse an SSE streaming response from AgentCore.

    The stream contains JSON events with contentBlockDelta text chunks.
    """
    text_parts = []
    for line in response["response"].iter_lines(chunk_size=10):
        if not line:
            continue
        decoded = line.decode("utf-8")
        if decoded.startswith("data: "):
            decoded = decoded[6:]
        try:
            event = json.loads(decoded)
            evt = event.get("event", event)
            delta = evt.get("contentBlockDelta", {}).get("delta", {})
            if "text" in delta:
                text_parts.append(delta["text"])
        except (json.JSONDecodeError, TypeError):
            text_parts.append(decoded)
    return "".join(text_parts)


def _parse_response(response) -> str:
    """Route to the correct parser based on content type."""
    content_type = response.get("contentType", "")

    if "text/event-stream" in content_type:
        return _parse_sse_response(response)

    chunks = []
    for chunk in response.get("response", []):
        if isinstance(chunk, bytes):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(str(chunk))
    raw = "".join(chunks)

    if content_type == "application/json":
        try:
            data = json.loads(raw)
            return data.get("response", raw)
        except (json.JSONDecodeError, TypeError):
            pass
    return raw


def invoke_trading_chat_agent(
    prompt: str,
    session_id: str | None = None,
    *,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
) -> str:
    """Invoke the TradingChatAgent on AgentCore and return the text response."""
    client = _get_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )
    session_id = session_id or str(uuid.uuid4())
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=TRADING_CHAT_AGENT_ARN,
        runtimeSessionId=session_id,
        payload=payload,
    )
    return _parse_response(response)


def invoke_market_analyst_agent(
    prompt: str,
    *,
    aws_access_key_id: str | None = None,
    aws_secret_access_key: str | None = None,
    aws_session_token: str | None = None,
) -> str:
    """Invoke the MarketAnalystAgent on AgentCore and return the text response."""
    client = _get_client(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_session_token=aws_session_token,
    )
    payload = json.dumps({"prompt": prompt}).encode()

    response = client.invoke_agent_runtime(
        agentRuntimeArn=MARKET_ANALYST_AGENT_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=payload,
    )
    return _parse_response(response)
