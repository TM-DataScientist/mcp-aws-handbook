import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from strands.types.content import Messages
from typing import List, Dict

# Variant of the RAG agent that merges:
# - generic AWS MCP tools
# - Bedrock Knowledge Base retrieval MCP tools
# into one unified toolset for the model.

# RAGエージェントクラス
class RagAgent:
    def __init__(self):
        """RAGエージェントを初期化"""
        # AAWS MCP Serverへの接続
        self.aws_mcp_client = self.create_stdio_mcp_client(
            command="uvx",
            args=[
                "mcp-proxy-for-aws@1.1.5",
                "https://aws-mcp.us-east-1.api.aws/mcp",
                "--metadata", "AWS_REGION=us-west-2"
            ],
            env={
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY":os.getenv("AWS_SECRET_ACCESS_KEY"),
            }
        )
        # AWS Bedrock Knowledge Base Retrieval MCP Serverへの接続設定
        self.aws_kb_mcp_client = self.create_stdio_mcp_client(
            command="uvx",  # uvxコマンドを使用してMCPサーバーを起動
            args=["awslabs.bedrock-kb-retrieval-mcp-server@1.0.13"],
            env={
                "AWS_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                "AWS_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
                "AWS_REGION": "us-west-2",  # AWSリージョン
            }
        )
    
    def create_stdio_mcp_client(self, command: str, args: List[str], env: Dict) -> MCPClient:
        """stdio MCPクライアントを作成する関数"""
        # All MCP servers are launched as subprocesses via stdio transport.
        stdio_mcp_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(command=command, args=args, env=env)
            ),
            startup_timeout=60
        )
        return stdio_mcp_client

    def create_agent(self, tools: list):
        # Keep model/tool/prompt configuration centralized.
        # エージェントを初期化
        return Agent(
            model=BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0"),
            system_prompt="AWSに関する質問はAWS MCP Serverを用いて、システム設計情報についてはBedrock Knowledge Retrieval Base MCP Serverを用いて回答してください。その参考先も明記してください。",
            tools=tools,
            callback_handler=None,
        )

    async def stream(self, messages: Messages):
        # Open both MCP sessions so their tool registries can be queried.
        with self.aws_mcp_client,  self.aws_kb_mcp_client:
            # Merge both tool lists; agent can choose from either source.
            tools = self.aws_mcp_client.list_tools_sync()
            tools.extend(self.aws_kb_mcp_client.list_tools_sync())

            # エージェントの生成
            agent = self.create_agent(
                tools=tools
            )

            # Pass through streamed message events to Streamlit layer.
            # メッセージの返答
            async for event in agent.stream_async(messages):
                if "message" in event:
                    yield event["message"]
