"""
MCP Prompts / Tools を使う Streamlit ホストのサンプル。
MCPClient から取得したツールを Strands Agent に渡して実行可能にする。
"""

# 処理の流れ:
# 1. stdio で tools サーバーを起動し、Prompt と Tool の一覧を MCPClient で取得する。
# 2. サイドバーで選択した Tool だけを Strands Agent に渡し、必要時に MCP 経由で実行させる。
# 3. Prompt で作った入力文とユーザー発話を組み合わせ、チャット応答を画面へ表示する。

import asyncio

import streamlit as st
from mcp import (
    ClientSession,
    GetPromptResult,
    ListPromptsResult,
    StdioServerParameters,
)
from mcp.client.stdio import stdio_client
from strands.agent import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPAgentTool, MCPClient
from strands.types.content import ContentBlock, Message


# デコレータ関数を定義
def with_mcp_client(func) -> ClientSession:
    """MCPClient のライフサイクル管理をデコレーター化する。"""

    async def wrapper(*args, **kwargs):
        # tools を提供するサーバーを stdio で起動する設定。
        server_params = StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                "../server",
                "3_tools_server.py",
            ],
            env={},
        )

        mcp_client = MCPClient(lambda: stdio_client(server_params))

        # context manager 内で prompt/tool API を同期メソッドとして扱える。
        with mcp_client:
            return await func(mcp_client, *args, **kwargs)

    return wrapper


@with_mcp_client
async def main(mcp_client: MCPClient):
    """Prompt と Tool を選択して Strands Agent へ渡す UI。"""

    st.title("Chat with MCP")

    # Prompts
    with st.sidebar:
        st.subheader("Prompts")
        list_prompts: ListPromptsResult = (
            mcp_client.list_prompts_sync()
        )  # MCP SDKを使用するときと異なる方法で指定
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
            result: GetPromptResult = mcp_client.get_prompt_sync(
                select_prompt_name, args=args
            )  # MCP SDKを使用するときと異なる方法で指定
            # prompt 本文を chat_input に流し込んで再利用する。
            st.session_state.chat_input = result.messages[0].content.text

    # 有効化する tool をチェックボックスで選択する。
    with st.sidebar:
        st.divider()
        st.subheader("Tools")
        list_tools = mcp_client.list_tools_sync()

        select_tool: list[MCPAgentTool] = []
        for tool in list_tools:
            if st.checkbox(tool.tool_name, value=True):
                select_tool.append(tool)

    if input := st.chat_input(
        key="chat_input"
    ):  # keyの指定を追加。該当のkeyで保持された値がセットされる
        user_content: list[ContentBlock] = []

        # ユーザー入力をエージェント向けメッセージへ変換する。
        user_content.append({"text": input})
        user_message: Message = {"role": "user", "content": user_content}

        for content in user_content:
            with st.chat_message("user"):
                st.write(content["text"])

        model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name="us-west-2",
        )

        # チェックされた MCP ツールだけをエージェントへ注入する。
        agent = Agent(
            model=model,
            tools=select_tool,  # ここを追加
            callback_handler=None,
        )

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
