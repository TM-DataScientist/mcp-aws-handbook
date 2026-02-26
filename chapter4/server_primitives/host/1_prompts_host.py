"""
MCP Prompts を使う Streamlit ホストのサンプル。
サイドバーでプロンプトを選び、生成文をチャット入力に反映して会話する。
"""

import asyncio

import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from strands.agent import Agent
from strands.models import BedrockModel
from strands.types.content import ContentBlock, Message


# デコレータ関数を定義
def with_mcp_client(func) -> ClientSession:
    """MCP サーバー接続の開始・初期化・終了を共通化する。"""

    async def wrapper(*args, **kwargs):
        # prompts サンプル用サーバーを stdio 経由で起動する。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                "../server",
                "1_prompts_server.py",
            ],
            env={},
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # MCP セッション開始時のハンドシェイクを行う。
                await session.initialize()

                return await func(session, *args, **kwargs)

    return wrapper


@with_mcp_client
async def main(session: ClientSession):
    """Prompt 一覧の取得とチャット実行を行う UI 本体。"""

    st.title("Chat with MCP")

    # サイドバーで prompt を選び、引数を入力して雛形文を作る。
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
            # 取得した prompt 本文を次回のチャット入力値としてセットする。
            st.session_state.chat_input = result.messages[0].content.text

    if input := st.chat_input(
        key="chat_input"
    ):  # keyの指定を追加。該当のkeyで保持された値がセットされる
        user_content: list[ContentBlock] = []

        # ユーザー発話を Strands メッセージ形式へ変換する。
        user_content.append({"text": input})
        user_message: Message = {"role": "user", "content": user_content}

        for content in user_content:
            with st.chat_message("user"):
                st.write(content["text"])

        model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name="us-west-2",
        )

        # 今回は MCP ツールを使わず、LLM 応答のみ実行する。
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
