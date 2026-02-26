"""
MCP Prompts と Resources を使う Streamlit ホストのサンプル。
選択したリソース本文をユーザー入力へ追加し、回答の文脈として利用する。
"""

import asyncio

import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import Resource
from strands.agent import Agent
from strands.models import BedrockModel
from strands.types.content import ContentBlock, Message


# デコレータ関数を定義
def with_mcp_client(func) -> ClientSession:
    """Resources サンプル用 MCP サーバー接続を共通化する。"""

    async def wrapper(*args, **kwargs):
        # resources を提供するサーバーを stdio で起動する。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                "../server",
                "2_resources_server.py",
            ],
            env={},
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # セッション初期化で prompt/resource API を利用可能にする。
                await session.initialize()

                return await func(session, *args, **kwargs)

    return wrapper


@with_mcp_client
async def main(session: ClientSession):
    """Prompt と Resource の選択を受けてチャットを実行する。"""

    st.title("Chat with MCP")

    # Prompts の選択・引数入力・チャット入力への反映。
    with st.sidebar:
        st.subheader("Prompts")
        list_prompts = await session.list_prompts()
        prompt_names = [prompt.name for prompt in list_prompts.prompts]
        select_prompt_name = st.selectbox("プロンプトを選択", prompt_names)

        select_prompt = list(
            filter(
                lambda x: x.name == select_prompt_name,
                list_prompts.prompts,
            )
        )[0]

        st.text("パラメーター")

        args = {}
        for argument in select_prompt.arguments:
            value = st.text_input(
                label=argument.name,
                placeholder=argument.description,
            )
            args[argument.name] = value

        if st.button("プロンプトをセット"):
            result = await session.get_prompt(
                select_prompt_name, arguments=args
            )  # MCPサーバーからPrompts情報を取得
            # 選択 prompt の本文を chat_input 初期値として設定する。
            st.session_state.chat_input = result.messages[0].content.text

    # Resources の選択。チェックした項目だけ会話コンテキストへ注入する。
    with st.sidebar:
        st.divider()
        st.subheader("Resources")
        list_resources = await session.list_resources()

        select_resource: list[Resource] = []

        for resource in list_resources.resources:
            if st.checkbox(resource.name):
                select_resource.append(resource)

    if input := st.chat_input(
        key="chat_input"
    ):  # keyの指定を追加。該当のkeyで保持された値がセットされる
        user_content: list[ContentBlock] = []

        # まずユーザーの自由入力を追加する。
        user_content.append({"text": input})
        user_message: Message = {"role": "user", "content": user_content}

        # 選択リソース本文を読み出し、同一メッセージ内に追記する。
        for resource in select_resource:
            if resource:
                result = await session.read_resource(uri=resource.uri)
                text = result.contents[0].text

                user_content.append({"text": text})

        for content in user_content:
            with st.chat_message("user"):
                st.write(content["text"])

        model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name="us-west-2",
        )

        # リソースを加えた入力をもとに回答を生成する。
        agent = Agent(model=model, callback_handler=None)

        agent_stream = agent.stream_async([user_message])

        async for event in agent_stream:
            if "message" in event:
                message: Message = event["message"]

                with st.chat_message(message["role"]):
                    for content in message["content"]:
                        if "text" in content:
                            st.write(content["text"])
                        else:
                            st.json(content, expanded=1)


if __name__ == "__main__":
    asyncio.run(main())
