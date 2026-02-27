"""
Prompt プリミティブを提供する MCP サーバーのサンプル。
翻訳指示文を動的に組み立て、host 側から呼び出せるようにする。
"""

# 処理の流れ:
# 1. FastMCP に Prompt を登録し、host から取得できる翻訳テンプレートを公開する。
# 2. Prompt 関数では引数を受け取り、会話入力へ流し込みやすい文章を返す。
# 3. mcp.run() でサーバー待ち受けを開始し、Prompt リクエストを処理する。

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MCP Server Example")


@mcp.prompt(title="Translation")
def translation(lang: str) -> str:
    """翻訳用の指示文テンプレートを生成する Prompt。"""

    # 実行ログとして prompt 呼び出しを標準出力へ出す。
    print("translation")
    # host 側はこのテンプレートをチャット入力として再利用する。
    return f"以下の文章を{lang}に訳してください。"


if __name__ == "__main__":
    mcp.run()
