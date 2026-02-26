import asyncio
import os
from mcp.client.stdio import stdio_client, StdioServerParameters
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.types import CallToolResult, TextContent
from typing import Dict, List
# DeepEvalによる評価で利用
from deepeval.test_case import LLMTestCase, MCPServer, MCPToolCall
from deepeval.metrics import MCPUseMetric
from deepeval.models import AmazonBedrockModel
from deepeval import evaluate

# This module demonstrates both:
# 1) running an MCP-enabled calculator agent
# 2) evaluating MCP tool-usage quality with DeepEval

# 数値計算エージェントクラス
class CalcAgent:
    def __init__(self):
        # 足し算、引き算するMCPサーバーとのクライアントを生成
        self.addsub_mcp_server = self.create_stdio_mcp_client(
            command="uv",  
            args=["run", "./addsub_server.py"],
        )
        # 掛け算、割り算するMCPサーバーとのクライアントを生成
        self.muldiv_mcp_server = self.create_stdio_mcp_client(
            command="uv",  
            args=["run", "./muldiv_server.py"],
        )

    def create_stdio_mcp_client(
        self, command: str, args: List[str], env: Dict = {}
    ) -> MCPClient:
        """Stdio MCPクライアントを作成する関数"""
        # Each local MCP server is launched as a child process via stdio.
        stdio_mcp_client = MCPClient(
            lambda: stdio_client(
                StdioServerParameters(command=command, args=args, env=env)
            ),
            startup_timeout=60,
        )
        return stdio_mcp_client

    def create_agent(self, tools: list) -> Agent:
        """利用可能なツールを使ってエージェントを作成"""
        system_prompt = (
            "MCPサーバーを活用して、ユーザの質問に回答してください"
        )
        # Bedrockのモデルを定義
        model = BedrockModel(model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0")
        return Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools,
            callback_handler=None,
        )

    async def invoke(self, query: str):
        """質問に対して回答を生成し、使用したツール情報も返す"""
        # Open both MCP server sessions while solving one query.
        with self.addsub_mcp_server, self.muldiv_mcp_server:
            # 各MCPクライアントから利用可能なツールを取得
            addsub_mcp_tools = self.addsub_mcp_server.list_tools_sync()
            muldiv_mcp_tools = self.muldiv_mcp_server.list_tools_sync()


            # 全てのツールを組み合わせてエージェントを作成・実行
            agent = self.create_agent(tools=addsub_mcp_tools + muldiv_mcp_tools)
            # Response object contains message and tool trace metrics.
            response = agent(query)
            return response, addsub_mcp_tools, muldiv_mcp_tools
        
def extract_tool_results(data):
    """エージェント実行データからツール使用結果を抽出"""
    # Walk trace cycles and normalize tool call/result pairs.
    results = []
    for cycle in data.get("traces", []):
        tools = collect_tools(cycle)
        results.extend(convert_tool_results(tools))
    return results

def collect_tools(cycle):
    """実行サイクルからツール情報を収集"""
    tools = {}
   
    for child in cycle.get("children", []):
        if not child or not child.get("message"):
            continue
           
        for content in child["message"].get("content", []):
            # ツール使用の記録
            if "toolUse" in content:
                tool_use = content["toolUse"]
                tools[tool_use["toolUseId"]] = {
                    "name": tool_use["name"],
                    "input": tool_use.get("input", {}),
                    "output": None,
                }
            # ツール結果の記録
            elif "toolResult" in content:
                tool_result = content["toolResult"]
                tool_id = tool_result["toolUseId"]
                if tool_id in tools:
                    result_content = tool_result.get("structuredContent", {})
                    tools[tool_id]["output"] = result_content.get("result")
   
    return tools

def convert_tool_results(tools):
    """ツール情報をMCPToolCall形式に変換"""
    results = []
   
    for tool in tools.values():
        if not (tool["name"] and tool["output"]):
            continue
           
        # CallToolResultオブジェクトを作成
        call_tool_result = CallToolResult(
            content=[TextContent(type="text", text=str(tool["output"]))],
            isError=False,
        )
       
        # 構造化データがある場合は追加
        if isinstance(tool["output"], dict):
            call_tool_result.structuredContent = tool["output"]
           
        # MCPToolCallオブジェクトを作成
        results.append(
            MCPToolCall(
                name=tool["name"],
                args=tool["input"],
                result=call_tool_result,
            )
        )

    return results

def get_deepeval_mcp_server(server_name, tools):
    """評価用のMCPServerオブジェクトを作成"""
    return MCPServer(
        server_name=server_name,
        available_tools=[t.mcp_tool for t in tools],
    )

async def eval_mcp_use(input, output, mcp_servers, call_tool_results):
    """MCPツールの使用状況を評価"""
 
    # テストケースを作成
    test_case = LLMTestCase(
        input=input,
        actual_output=output["content"][0]["text"],
        mcp_servers=mcp_servers,
        mcp_tools_called=call_tool_results,
    )

    # 評価モデルを初期化
    deepeval_model = AmazonBedrockModel(
        model="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        region="us-west-2",
        cost_per_input_token=0.000001,
        cost_per_output_token=0.000005,
    )
   
    # MCPの使用状況を評価
    mcp_use_metrics = MCPUseMetric(threshold=0.8, model=deepeval_model, include_reason=True)
    evaluate(test_cases=[test_case], metrics=[mcp_use_metrics])
    # Close evaluator model to release network/session resources.
    await deepeval_model.close()

def evaluateAgent():
    """メイン実行関数：数値計算エージェントの動作例とMCP評価のデモ"""
    # 数値計算エージェントを初期化
    calc_agent = CalcAgent()
   
    # テスト用クエリ
    query = "3+4+5/5="
   
    # エージェントを実行して回答と使用ツール情報を取得
    response, addsub_mcp_tools, muldiv_mcp_tools = asyncio.run(calc_agent.invoke(query))
   
    # ツール実行結果を抽出
    call_tool_results = extract_tool_results(response.metrics.get_summary())
   
    # 評価用のMCPサーバーを作成
    mcp_servers = [
        get_deepeval_mcp_server("addsub_mcp_server", addsub_mcp_tools),
        get_deepeval_mcp_server("muldiv_mcp_server", muldiv_mcp_tools),
    ]
   
    # MCPツールの使用状況を評価
    asyncio.run(eval_mcp_use(query, response.message, mcp_servers, call_tool_results))
    # asyncio.run(eval_mcp_use(query, response.message, mcp_servers, call_tool_results[1:]))

if __name__ == "__main__":
    evaluateAgent()
