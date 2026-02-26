from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# Minimal client sample:
# - connect to AgentCore Gateway over IAM-authenticated streamable HTTP
# - collect all advertised tools (with pagination)
# - execute a conversion prompt through Strands Agent

# AgentCore Gateway エンドポイント
GATEWAY_ENDPOINT = "<AgentCore Gatewayのエンドポイント>"

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
# PROMPT="""以下のJSONをYAMLに変換して結果だけ出力してください
# [{"a": {"aa": "1", "ab": "5"}, "b": "2", "c": "3"}]"""
# PROMPT="""CSVを変換するツールを1つ検索して"""

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
