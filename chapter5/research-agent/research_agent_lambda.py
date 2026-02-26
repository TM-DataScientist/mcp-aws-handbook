import os
from typing import Dict, List
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient

# Lambda-friendly variant of the research agent.
# The core behavior matches `research_agent.py`, with an additional
# `lambda_handler` entrypoint for Step Functions / EventBridge integration.

# タイムアウト時間
STARTUP_TIMEOUT = 90


def create_stdio_mcp_client(command: str, args: List[str], env: Dict) -> MCPClient:
    """stdio MCPクライアントを作成"""
    # Standard process-based MCP client (for Sequential Thinking server).
    return MCPClient(
        lambda: stdio_client(
            StdioServerParameters(command=command, args=args, env=env)
        ),
        startup_timeout=STARTUP_TIMEOUT
    )


def create_streamable_http_mcp_client(url: str) -> MCPClient:
    """Streamable HTTP MCPクライアントを作成"""
    # HTTP transport MCP client (for Tavily-hosted endpoint).
    return MCPClient(
        lambda: streamable_http_client(url),
        startup_timeout=STARTUP_TIMEOUT
    )

class ResearchAgent:
    """技術トレンドリサーチエージェント"""


    SYSTEM_PROMPT = """
ユーザープロンプトで指定された日付を基準とした日本における技術トピックを深掘りした調査レポートをMarkdown形式で作成してください。
調査レポートはトピックごとに分けて、最大5個の技術トピックを深堀して、まとめてください。
- 条件
  - Tavily MCP ServerとSequential Thinking MCP Serverを用いてください
  - 必要な情報は、Tavily MCP Serverを用いたWeb検索で収集してください
  - Tavily検索が合計10回以下になるように計画して調査レポートを作成してください
  - 検索結果をSequential Thinking MCP Serverで都度精査し、不十分であると判断したときは制限回数の中で再検索してください
  - 対象とする技術トレンドは指定日から過去1週間のみに限定としてください
  - 各技術トピックの説明に、そのトピックを選ぶ要因となった理由を明記してください
  - 参考にしたサイトのリンクを必ず記載してください
"""
    def __init__(self):
        # Fail fast if Tavily credential is missing.
        self.tavily_api_key = os.getenv("TAVILY_API_KEY")
        if not self.tavily_api_key:
            raise ValueError("TAVILY_API_KEY環境変数が設定されていません")
       
        """MCPクライアントの設定"""
        # Sequential Thinking用のstdioクライアント
        self.sequential_thinking_client = create_stdio_mcp_client(
            command="npx",
            args=["-y", "@modelcontextprotocol/server-sequential-thinking@2025.12.18", "--prefix", "/tmp"],
            env={}
        )
        # Tavily検索用のHTTPクライアント
        tavily_url = f"https://mcp.tavily.com/mcp/?tavilyApiKey={self.tavily_api_key}"
        self.tavily_client = create_streamable_http_mcp_client(tavily_url)

    def create_agent(self, tools: List) -> Agent:
        """Strands Agentを作成"""
        # Bedrockのモデルを定義
        model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
        # Prompt + tool injection happen here in one place.
        return Agent(
            model=model,
            system_prompt=self.SYSTEM_PROMPT,
            tools=tools,
        )

    def generate_report(self, query: str):
        """調査レポートを生成"""
        try:
            # MCPクライアントセッションを開始
            with self.tavily_client, self.sequential_thinking_client:
                # 利用可能なツールを収集
                tools = []
                tools.extend(self.tavily_client.list_tools_sync())
                tools.extend(self.sequential_thinking_client.list_tools_sync())

                # エージェントを作成してレポート生成を開始
                agent = self.create_agent(tools)
                # Execute query against Bedrock model with MCP tool-calling enabled.
                content = agent(query)


                return content
        except Exception as e:
            print(f"エラーが発生しました: {e}")

if __name__ == "__main__":
    # 調査基準日を指定
    from datetime import date
    date = date.today().strftime("%Y-%m-%d")
    agent = ResearchAgent()
    agent.generate_report(date)

def lambda_handler(event, context):
    # Lambda input contract: the event must include `date`.
    date = event.get("date")
    if not date:
        return {"error": "dateパラメータが必要です"}

    # Recreate the agent per invocation to keep function stateless.
    agent = ResearchAgent()
    response = agent.generate_report(date)
    # Stringify for simple JSON-serializable response payload.
    return str(response)
