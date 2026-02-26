"""
streamable-http 接続で MCP サーバーと連携する Streamlit ホストのサンプル。
標準入出力の代わりに HTTP エンドポイント経由で Prompt/Tool を利用する。
"""

import asyncio

import streamlit as st
from mcp import (
    ClientSession,
    GetPromptResult,
    ListPromptsResult,
)
from mcp.client.streamable_http import streamable_http_client
from strands.agent import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPAgentTool, MCPClient
from strands.types.content import ContentBlock, Message


def with_mcp_client(func) -> ClientSession:
    """streamable-http 経由で MCPClient を初期化するデコレーター。"""

    async def wrapper(*args, **kwargs):
        # HTTP エンドポイントの MCP サーバーに接続する。
        mcp_client = MCPClient(
            lambda: streamable_http_client(url="http://localhost:8000/mcp")
        )  # streamable_http_clientからMCPClientを生成するよう変更
        # context manager で接続開始/終了を自動化する。
        with mcp_client:
            return await func(mcp_client, *args, **kwargs)

    return wrapper


@with_mcp_client
async def main(mcp_client: MCPClient):
    """HTTP 接続された MCP サーバーと対話する UI 本体。"""

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
            # 取得した prompt 文を chat_input の既定値として使う。
            st.session_state.chat_input = result.messages[0].content.text

    # 利用する tool をサイドバーで選択する。
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

        # ユーザー発話を Strands の Message 形式へ変換する。
        user_content.append({"text": input})
        user_message: Message = {"role": "user", "content": user_content}

        for content in user_content:
            with st.chat_message("user"):
                st.write(content["text"])

        model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name="us-west-2",
        )

        # 選択された MCP ツールを有効化して回答を生成する。
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
