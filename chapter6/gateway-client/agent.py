import os
from pathlib import Path

def load_env_file() -> None:
    # `uv run path/to/script.py` from the repo root does not automatically load `.env`.
    candidate_paths = [Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"]
    for env_path in candidate_paths:
        if not env_path.is_file():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
        return

load_env_file()

try:
    from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
except ImportError:
    import boto3
    import httpx
    from botocore.auth import SigV4Auth as BotocoreSigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials
    from mcp.client.streamable_http import streamablehttp_client

    class AwsSigV4Auth(httpx.Auth):
        requires_request_body = True

        def __init__(self, aws_service: str, aws_region: str):
            self._aws_service = aws_service
            self._aws_region = aws_region
            self._session = boto3.Session(region_name=aws_region)

        def _get_credentials(self) -> Credentials:
            access_key = os.getenv("AWS_ACCESS_KEY_ID")
            secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            session_token = os.getenv("AWS_SESSION_TOKEN")
            if access_key and secret_key:
                return Credentials(access_key, secret_key, session_token)

            credentials = self._session.get_credentials()
            if credentials is None:
                raise RuntimeError("AWS credentials were not found.")
            return credentials.get_frozen_credentials()

        def auth_flow(self, request: httpx.Request):
            # Sign only stable headers. httpx/httpcore may rewrite transport
            # headers such as `connection` and `accept-encoding`, which breaks
            # SigV4 verification if they are included in SignedHeaders.
            stable_headers = {}
            for header_name in ("host", "accept", "content-type"):
                if header_name in request.headers:
                    stable_headers[header_name] = request.headers[header_name]

            signed_request = AWSRequest(
                method=request.method,
                url=str(request.url),
                data=request.content,
                headers=stable_headers,
            )
            BotocoreSigV4Auth(
                self._get_credentials(),
                self._aws_service,
                self._aws_region,
            ).add_auth(signed_request)
            request.headers.update(signed_request.headers.items())
            yield request

    def aws_iam_streamablehttp_client(
        endpoint: str,
        aws_service: str = "bedrock-agentcore",
        aws_region: str = "us-west-2",
        terminate_on_close: bool = True,
    ):
        return streamablehttp_client(
            endpoint,
            auth=AwsSigV4Auth(aws_service=aws_service, aws_region=aws_region),
            terminate_on_close=terminate_on_close,
        )

from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Minimal client sample:
# - connect to AgentCore Gateway over IAM-authenticated streamable HTTP
# - collect all advertised tools (with pagination)
# - execute a conversion prompt through Strands Agent

# AgentCore Gateway エンドポイント
GATEWAY_ENDPOINT = "https://format-transformer-dwz7n5cw4j.gateway.bedrock-agentcore.us-west-2.amazonaws.com/mcp"

def create_aws_iam_streamable_http_mcp_client(
    url: str, 
    aws_service: str = "bedrock-agentcore"
) -> MCPClient:
    """MCP Proxy for AWSを利用したMCPクライアントを作成する関数"""
    # Wrap the IAM-authenticated HTTP transport in MCPClient.
    streamable_http_mcp_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=url,
            aws_service=aws_service,
            aws_region="us-west-2", 
        )
    )
    return streamable_http_mcp_client

def get_tools_list(client: MCPClient):
    """AgentCore Gatewayのツール一覧を取得する"""
    more_tools = True
    tools = []
    pagination_token = None
    # ページネーションを使用してすべてのツールを取得
    while more_tools:
        # Keep requesting subsequent pages until no token is returned.
        tmp_tools = client.list_tools_sync(pagination_token=pagination_token)
        tools.extend(tmp_tools)
        if tmp_tools.pagination_token is None:
            more_tools = False
        else:
            more_tools = True
            pagination_token = tmp_tools.pagination_token
    return tools

PROMPT="""こんにちは。以下のjsonをcsvに変換して結果だけ出力してください
[{"a": "1", "b": "2", "c": "3"}]"""
PROMPT="""以下のJSONをYAMLに変換して結果だけ出力してください
[{"a": {"aa": "1", "ab": "5"}, "b": "2", "c": "3"}]"""
PROMPT="""CSVを変換するツールを1つ検索して"""

def invoke_agent():
    """メイン処理：エージェントを起動してデータ変換を実行"""

    # MCPクライアントを作成し、ゲートウェイに接続
    mcp_client = create_aws_iam_streamable_http_mcp_client(
        GATEWAY_ENDPOINT,
    )
    with mcp_client:
        # 利用可能なツール一覧を取得
        mcp_tools = get_tools_list(mcp_client)
        # Create a model-backed agent that can call any gateway-provided tool.
        # Bedrockのモデルを定義
        model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
        # エージェントを初期化
        agent = Agent(
            model=model,
            tools=mcp_tools
        )
        # Prompt execution performs tool selection and conversion.
        agent(PROMPT)

if __name__ == "__main__":
    invoke_agent()
