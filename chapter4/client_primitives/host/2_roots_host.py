"""
Sampling に加えて Roots 機能を扱う MCP ホストのサンプル。
サーバーへ作業ディレクトリ情報を渡し、出力先の基準パスとして使わせる。
"""

# 処理の流れ:
# 1. Sampling と Roots の callback を登録した状態で MCP サーバーへ接続する。
# 2. Sampling 要求は Bedrock で処理し、Roots 要求には現在の作業ディレクトリを返す。
# 3. translate ツール実行時に、サーバーが出力先として使うルート情報も host 側から渡す。

import asyncio
import os
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
    """Sampling と Roots のコールバック付きで MCP 接続を確立する。"""

    async def wrapper(*args, **kwargs):
        # スクリプト位置を基準に server ディレクトリを解決し、実行場所に依存しないようにする。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                str(SERVER_DIR),
                "2_roots_server.py",
            ],
            env={},
        )

        async with stdio_client(server_params) as (read, write):
            # sampling/list_roots の 2 種類のリクエストを host 側で受ける。
            async with ClientSession(
                read,
                write,
                sampling_callback=handle_sampling_callback,
                list_roots_callback=handle_roots_callback,
                # Rootsリクエストを処理する関数を指定
            ) as session:
                await session.initialize()

                return await func(session, *args, **kwargs)

    return wrapper


async def handle_sampling_callback(
    context: RequestContext,
    request_params: types.CreateMessageRequestParams,
) -> types.CreateMessageResult:
    """Sampling 要求を受けて Bedrock で応答文を生成する。"""

    # 受信パラメーターを可視化して動作確認しやすくする。
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

    # 生成結果を MCP の CreateMessageResult として返却する。
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
    """サーバーが利用できる作業ルートを 1 件返す。"""

    # 現在の作業ディレクトリを file URI 形式で渡す。
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


@with_mcp_client
async def main(session: ClientSession):
    """translate ツールの入力を集め、結果を表示する。"""

    tool_name = "translate"

    # サーバー側ツール情報を取得する。
    tools = await session.list_tools()

    translate_tool = next(
        (t for t in tools.tools if t.name == tool_name),
        None,
    )

    content = f"[bold blue]{translate_tool.name}[/bold blue]\n"
    content += f"[dim]{translate_tool.description}[/dim]"

    print(Panel(content, title="Tool info"))

    # スキーマ定義から入力欄を生成して引数辞書を構築する。
    params = {}
    for param_name, param_info in translate_tool.inputSchema["properties"].items():
        value = Prompt.ask(f"[yellow]{param_name}[/yellow]")
        params[param_name] = value

    # ツール実行結果をそのまま表示する。
    result = await session.call_tool(translate_tool.name, params)
    print(Panel(result.content[0].text, title="Tool Result"))


if __name__ == "__main__":
    asyncio.run(main())
