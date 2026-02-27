"""
MCP Prompts と Resources を使う Streamlit ホストのサンプル。
選択したリソース本文をユーザー入力へ追加し、補足情報付きで会話する。
"""

# 処理の流れ:
# 1. リポジトリルートの .env を読み込み、Bedrock 用の環境変数を host プロセスへ反映する。
# 2. stdio で resources サーバーを起動し、Prompt 一覧と Resource 一覧を UI に表示する。
# 3. 選択された Resource 本文をユーザー入力へ追加し、補足文脈つきで Bedrock に渡す。

import asyncio
import os
from pathlib import Path

import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Resource
from strands.agent import Agent
from strands.models import BedrockModel
from strands.types.content import ContentBlock, Message

ROOT_DIR = Path(__file__).resolve().parents[3]
SERVER_DIR = Path(__file__).resolve().parent.parent / "server"

DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
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


def with_mcp_client(func):
    """resources サーバー接続の開始と終了を共通化する。"""

    async def wrapper(*args, **kwargs):
        # .env から読み込んだ環境変数も含めて server 側へ引き継ぐ。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                str(SERVER_DIR),
                "2_resources_server.py",
            ],
            env=dict(os.environ),
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Prompt / Resource API を使える状態にしてから本処理へ渡す。
                await session.initialize()
                return await func(session, *args, **kwargs)

    return wrapper


@with_mcp_client
async def main(session: ClientSession):
    """Prompt と Resource の選択を受けてチャット応答を生成する。"""

    st.title("Chat with MCP")

    # Prompt 一覧を表示し、入力テンプレートを chat_input へ反映できるようにする。
    with st.sidebar:
        st.subheader("Prompts")
        list_prompts = await session.list_prompts()
        prompt_names = [prompt.name for prompt in list_prompts.prompts]
        selected_prompt_name = st.selectbox("Select prompt", prompt_names)
        selected_prompt = next(
            prompt
            for prompt in list_prompts.prompts
            if prompt.name == selected_prompt_name
        )

        st.text("Parameters")
        args = {}
        for argument in selected_prompt.arguments:
            value = st.text_input(
                label=argument.name,
                placeholder=argument.description,
            )
            args[argument.name] = value

        # Prompt 本文をそのまま次回入力の初期値として使う。
        if st.button("Set prompt"):
            prompt_result = await session.get_prompt(
                selected_prompt_name,
                arguments=args,
            )
            st.session_state.chat_input = prompt_result.messages[0].content.text

    # Resource はチェックしたものだけを会話コンテキストへ注入する。
    with st.sidebar:
        st.divider()
        st.subheader("Resources")
        list_resources = await session.list_resources()
        selected_resources: list[Resource] = []

        for resource in list_resources.resources:
            if st.checkbox(resource.name):
                selected_resources.append(resource)

    # ユーザー入力が送信されたタイミングで 1 ターンの推論を実行する。
    if user_text := st.chat_input(key="chat_input"):
        user_content: list[ContentBlock] = [{"text": user_text}]
        user_message: Message = {"role": "user", "content": user_content}

        # 選択された Resource 本文を読み出し、同じ user message 内へ追記する。
        for resource in selected_resources:
            resource_result = await session.read_resource(uri=resource.uri)
            resource_text = resource_result.contents[0].text
            user_content.append({"text": resource_text})

        for content in user_content:
            with st.chat_message("user"):
                st.write(content["text"])

        # .env があればモデル ID とリージョンをそこから取得して使う。
        model = BedrockModel(
            model_id=os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID),
            region_name=os.getenv(
                "AWS_REGION",
                os.getenv("AWS_DEFAULT_REGION", DEFAULT_REGION),
            ),
        )
        # Resource を含む拡張済み入力を使って応答を生成する。
        agent = Agent(model=model, callback_handler=None)
        agent_stream = agent.stream_async([user_message])

        async for event in agent_stream:
            if "message" not in event:
                continue
            message: Message = event["message"]
            with st.chat_message(message["role"]):
                for content in message["content"]:
                    if "text" in content:
                        st.write(content["text"])
                    else:
                        st.json(content, expanded=1)


if __name__ == "__main__":
    asyncio.run(main())
