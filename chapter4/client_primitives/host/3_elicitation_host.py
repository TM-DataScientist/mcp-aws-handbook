"""
Sampling / Roots / Elicitation をまとめて扱う MCP ホストのサンプル。
サーバーから追加入力が必要なときに、対話で値を収集して返す。
"""

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.shared.context import RequestContext
from pydantic import FileUrl
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from strands.agent import Agent
from strands.models import BedrockModel


def with_mcp_client(func) -> ClientSession:
    """Sampling / Roots / Elicitation の各コールバックを設定して接続する。"""

    async def wrapper(*args, **kwargs):
        # Elicitation サンプル用サーバーを stdio 経由で起動する。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                "../server",
                "3_elicitation_server.py",
            ],
            env={},
        )

        async with stdio_client(server_params) as (read, write):
            # サーバーが要求する 3 種類の client primitive に応答できるように登録する。
            async with ClientSession(
                read,
                write,
                sampling_callback=handle_sampling_callback,
                list_roots_callback=handle_roots_callback,
                elicitation_callback=handle_elicitation_callback,
                # Elicitationリクエストを処理する関数を指定
            ) as session:
                await session.initialize()

                return await func(session, *args, **kwargs)

    return wrapper


async def handle_sampling_callback(
    context: RequestContext,
    request_params: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    """Sampling 要求に対して Bedrock 推論を実行して結果を返す。"""

    # 推論条件を表示して、サーバーから渡された内容を確認する。
    content = f"[cyan]System Prompt:[/cyan] {request_params.systemPrompt}\n"
    content += f"[cyan]Temperature:[/cyan] {request_params.temperature}\n"
    content += f"[cyan]Max Tokens:[/cyan] {request_params.maxTokens}\n"
    content += f"[cyan]Message:[/cyan] {request_params.messages[0].content.text}"

    print(Panel(content, title="Sampling parameters"))

    send_contents = [{"text": msg.content.text} for msg in request_params.messages]
    # list[ContentBlock]型に変換 [{"text: "LLMに送信する内容"}...] の形式

    # このサンプルでは Bedrock の Nova Lite を利用する。
    model_id = "us.amazon.nova-2-lite-v1:0"

    model = BedrockModel(
        model_id=model_id,
        region_name="us-west-2",
        max_tokens=request_params.maxTokens,
        temperature=request_params.temperature,
    )

    agent = Agent(
        model=model,
        system_prompt=request_params.systemPrompt,
        callback_handler=None,
    )

    response = agent(send_contents)

    # MCP 仕様に沿った形式で応答を返却する。
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text=response.message["content"][0]["text"],
        ),
        model=model_id,
        stopReason=response.stop_reason,
    )


async def handle_roots_callback(
    context: RequestContext,
) -> types.ListRootsResult:
    """サーバーへ現在の作業ディレクトリを Roots として通知する。"""

    work_dir = Path.cwd().as_uri()

    print(Panel(work_dir, title="Roots"))

    return types.ListRootsResult(
        roots=[
            types.Root(
                uri=FileUrl(work_dir),
                name="working directory",
            ),
        ],
    )


async def handle_elicitation_callback(
    context: RequestContext,
    request_params: types.ElicitRequestParams,
) -> types.ElicitResult:
    """サーバーからの追加入力依頼を受け、ユーザー入力を返す。"""

    # どの項目が必要かを見やすく表示する。
    content = f"[cyan]Message:[/cyan] {request_params.message}\n\n[cyan]Required fields:[/cyan]\n"
    for name, info in request_params.requestedSchema["properties"].items():
        content += f"  • {name}: {info.get('description', '')}\n"

    print(Panel(content, title="Elicit parameters"))

    # 要求されたスキーマに従って値を収集する。
    response_params = {}
    for name, info in request_params.requestedSchema["properties"].items():
        value = Prompt.ask(f"[yellow]{name}[/yellow] ({info.get('description', '')})")
        response_params[name] = value

    return types.ElicitResult(
        action="accept",
        content=response_params,
    )


@with_mcp_client
async def main(session: ClientSession):
    """translate ツールを対話的に呼び出す実行関数。"""

    tool_name = "translate"

    # サーバー提供ツールの中から translate を特定する。
    tools = await session.list_tools()

    translate_tool = next(
        (t for t in tools.tools if t.name == tool_name),
        None,
    )

    content = f"[bold blue]{translate_tool.name}[/bold blue]\n"
    content += f"[dim]{translate_tool.description}[/dim]"

    print(Panel(content, title="Tool info"))

    # ツール入力スキーマを元に引数を集める。
    params = {}
    for param_name, param_info in translate_tool.inputSchema["properties"].items():
        value = Prompt.ask(f"[yellow]{param_name}[/yellow]")
        params[param_name] = value

    # 実行結果テキストをパネル表示する。
    result = await session.call_tool(translate_tool.name, params)
    print(Panel(result.content[0].text, title="Tool Result"))


if __name__ == "__main__":
    asyncio.run(main())
