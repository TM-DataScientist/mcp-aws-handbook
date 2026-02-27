"""
MCP 連携なしの Streamlit チャット基礎版。
Bedrock モデルへメッセージを送り、ストリーム表示する最小構成を示す。
"""

# 処理の流れ:
# 1. Streamlit から受け取ったユーザー入力を Strands の Message 形式へ変換する。
# 2. MCP を使わず Bedrock モデルだけで応答を生成し、ストリームで受信する。
# 3. 生成されたメッセージをチャット UI へ順次描画し、最小構成の動きを確認する。

import asyncio

import streamlit as st
from strands.agent import Agent
from strands.models import BedrockModel
from strands.types.content import ContentBlock, Message


async def main():
    """ユーザー入力を Bedrock に送り、ストリーミング応答を画面表示する。"""

    st.title("Chat with MCP")

    # チャット入力があるタイミングで 1 ターン処理を開始する。
    if input := st.chat_input():
        user_content: list[ContentBlock] = []

        # Strands のメッセージ形式に合わせてユーザー入力を整形する。
        user_content.append({"text": input})
        user_message: Message = {"role": "user", "content": user_content}

        # 送信前にユーザー発話をチャット欄へ表示する。
        for content in user_content:
            with st.chat_message("user"):
                st.write(content["text"])

        # 利用する Bedrock モデルを初期化する。
        model = BedrockModel(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            region_name="us-west-2",
        )

        # ツールなしのシンプルなエージェントを生成する。
        agent = Agent(model=model, callback_handler=None)

        # ストリーム形式でモデル応答を受け取る。
        agent_stream = agent.stream_async([user_message])

        async for event in agent_stream:
            if "message" in event:
                message: Message = event["message"]

                # 応答内の各コンテンツブロックを順に描画する。
                with st.chat_message(message["role"]):
                    for content in message["content"]:
                        if "text" in content:
                            st.write(content["text"])
                        else:
                            st.json(content, expanded=1)


if __name__ == "__main__":
    asyncio.run(main())
