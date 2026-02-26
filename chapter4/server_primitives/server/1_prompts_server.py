"""
Prompt プリミティブを提供する MCP サーバーのサンプル。
翻訳指示文を動的に組み立て、host 側から呼び出せるようにする。
"""

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
