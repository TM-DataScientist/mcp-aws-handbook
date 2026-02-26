import asyncio
import nest_asyncio
import streamlit as st
from agent import RagAgent

# Streamlit runs an event loop already in some environments.
# `nest_asyncio` allows this script to call `asyncio.run(...)` safely.
nest_asyncio.apply()

# Streamlitのページ設定
st.set_page_config(page_title="RAGチャットアプリ", page_icon="🤖")

# タイトルを描画
st.title("RAGチャットアプリ")

# 会話履歴の初期化
if "messages" not in st.session_state:
    st.session_state.messages = []

# RAGAgentの初期化
if "agent" not in st.session_state:
    st.session_state.agent = RagAgent()

def print_message(message):
    # Render one chat message and expose tool traces in expandable sections.
    with st.chat_message(message["role"]):
        for content in message["content"]:
            if "text" in content:
                st.write(content["text"])
            if "toolUse" in content:
                with st.expander("toolUse", expanded=False):
                    st.write(content["toolUse"])
            if "toolResult" in content:
                with st.expander("toolResult", expanded=False):
                    st.write(content["toolResult"])

async def main():
    # Repaint all stored messages on each Streamlit rerun.
    # 会話履歴の表示
    for message in st.session_state.messages:
        print_message(message)

    # チャット入力
    if prompt := st.chat_input("質問を入力してください..."):
        # ユーザーメッセージを追加
        st.session_state.messages.append({"role": "user", "content": [{"text": prompt}]})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            with st.spinner("回答を生成中..."):
                # Stream responses token-by-token/event-by-event from backend agent.
                async for message in st.session_state.agent.stream(st.session_state.messages):
                    print_message(message)
                    # Persist assistant/tool events so they survive Streamlit reruns.
                    st.session_state.messages.append(message)

        except Exception as e:
            st.write(f"エラーが発生しました: {e}")
        
if __name__ == "__main__":
    asyncio.run(main())
