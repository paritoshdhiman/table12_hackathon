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
    """True only when AGENTCORE_ENABLED env var is set.

    Defaults to False so the app uses local Bedrock API multi-agent mode,
    which works without additional IAM permissions for AgentCore.
    """
    import os
    return os.environ.get("AGENTCORE_ENABLED", "").lower() in ("1", "true", "yes")


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

    content_type = response.get("contentType", "")

    if "text/event-stream" in content_type:
        content = []
        for line in response["response"].iter_lines(chunk_size=10):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    content.append(line[6:])
        return "\n".join(content)

    elif content_type == "application/json":
        chunks = []
        for chunk in response.get("response", []):
            chunks.append(chunk.decode("utf-8"))
        raw = "".join(chunks)
        try:
            data = json.loads(raw)
            return data.get("response", raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    else:
        chunks = []
        for chunk in response.get("response", []):
            if isinstance(chunk, bytes):
                chunks.append(chunk.decode("utf-8"))
            else:
                chunks.append(str(chunk))
        return "".join(chunks) if chunks else str(response)


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

    content_type = response.get("contentType", "")

    if "text/event-stream" in content_type:
        content = []
        for line in response["response"].iter_lines(chunk_size=10):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    content.append(line[6:])
        return "\n".join(content)

    elif content_type == "application/json":
        chunks = []
        for chunk in response.get("response", []):
            chunks.append(chunk.decode("utf-8"))
        raw = "".join(chunks)
        try:
            data = json.loads(raw)
            return data.get("response", raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    else:
        chunks = []
        for chunk in response.get("response", []):
            if isinstance(chunk, bytes):
                chunks.append(chunk.decode("utf-8"))
            else:
                chunks.append(str(chunk))
        return "".join(chunks) if chunks else str(response)
