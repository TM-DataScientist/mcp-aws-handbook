"""
Sampling 機能を持つ MCP ホストのサンプル。
サーバーからの Sampling 要求を受け、Bedrock モデルで応答を生成する。
"""

# 処理の流れ:
# 1. stdio で Sampling サーバーを起動し、host 側の callback を登録して接続する。
# 2. サーバーから Sampling 要求が来たら Bedrock へ渡し、生成結果を MCP 形式で返す。
# 3. translate ツールの入力を集めて呼び出し、翻訳結果をコンソールへ表示する。

import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.shared.context import RequestContext
from rich import print
from rich.panel import Panel
from rich.prompt import Prompt
from strands.agent import Agent
from strands.models import BedrockModel

ROOT_DIR = Path(__file__).resolve().parents[3]
SERVER_DIR = Path(__file__).resolve().parent.parent / "server"

DEFAULT_MODEL_ID = "us.amazon.nova-2-lite-v1:0"
DEFAULT_REGION = "us-west-2"


def load_dotenv_file(env_path: Path) -> None:
    """.env にある KEY=VALUE 形式の設定を環境変数へ読み込む。"""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        # 空行・コメント行・不正形式の行は設定値として扱わない。
        if not line or line.startswith("#") or "=" not in line:
            continue

        # 最初の = だけで分割し、値側に = を含むケースも壊さない。
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv_file(ROOT_DIR / ".env")


def with_mcp_client(func) -> ClientSession:
    """MCP サーバー接続の生成と初期化を共通化するデコレーター。"""

    async def wrapper(*args, **kwargs):
        # スクリプト位置を基準に server ディレクトリを解決し、実行場所に依存しないようにする。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                str(SERVER_DIR),
                "1_sampling_server.py",
            ],
            env={},
        )

        async with stdio_client(server_params) as (read, write):
            # sampling_callback を登録することで、サーバーからの推論要求を host 側で処理できる。
            async with ClientSession(
                read,
                write,
                sampling_callback=handle_sampling_callback,
                # Samplingリクエストを処理する関数を指定
            ) as session:
                await session.initialize()

                return await func(session, *args, **kwargs)

    return wrapper


async def handle_sampling_callback(
    context: RequestContext,
    request_params: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    """サーバーから渡された Sampling 要求を Bedrock で実行して返す。"""

    # デバッグしやすいように、受信した推論条件をパネルで表示する。
    content = f"[cyan]System Prompt:[/cyan] {request_params.systemPrompt}\n"
    content += f"[cyan]Temperature:[/cyan] {request_params.temperature}\n"
    content += f"[cyan]Max Tokens:[/cyan] {request_params.maxTokens}\n"
    content += f"[cyan]Message:[/cyan] {request_params.messages[0].content.text}"

    print(Panel(content, title="Sampling parameters"))

    send_contents = [{"text": msg.content.text} for msg in request_params.messages]
    # list[ContentBlock]型に変換 [{"text: "LLMに送信する内容"}...] の形式

    # .env があればモデル ID とリージョンをそこから取得して使う。
    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)

    model = BedrockModel(
        model_id=model_id,
        region_name=os.getenv(
            "AWS_REGION",
            os.getenv("AWS_DEFAULT_REGION", DEFAULT_REGION),
        ),
        max_tokens=request_params.maxTokens,
        temperature=request_params.temperature,
    )

    agent = Agent(
        model=model,
        system_prompt=request_params.systemPrompt,
        callback_handler=None,
    )

    response = agent(send_contents)

    # MCP が要求する型に詰め替えてサーバーへ返却する。
    return types.CreateMessageResult(
        role="assistant",
        content=types.TextContent(
            type="text",
            text=response.message["content"][0]["text"],
        ),
        model=model_id,
        stopReason=response.stop_reason,
    )


@with_mcp_client
async def main(session: ClientSession):
    """translate ツールの情報表示と呼び出しを行うエントリーポイント。"""

    tool_name = "translate"

    # サーバー公開ツール一覧から translate を検索する。
    tools = await session.list_tools()
    # tools.tools の中から、name == tool_name を満たす最初の要素を 1 件だけ取り出す
    translate_tool = next(
        (t for t in tools.tools if t.name == tool_name),
        None,
    )

    content = f"[bold blue]{translate_tool.name}[/bold blue]\n"
    content += f"[dim]{translate_tool.description}[/dim]"

    print(Panel(content, title="Tool info"))

    # inputSchema を使って必要パラメーターを動的に入力させる。
    params = {}
    for param_name, param_info in translate_tool.inputSchema["properties"].items():
        value = Prompt.ask(f"[yellow]{param_name}[/yellow]")
        params[param_name] = value

    # 収集した引数でツールを実行する。
    result = await session.call_tool(translate_tool.name, params)
    print(Panel(result.content[0].text, title="Tool Result"))


if __name__ == "__main__":
    asyncio.run(main())
