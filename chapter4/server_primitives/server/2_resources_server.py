"""
Prompt と Resource を提供する MCP サーバーのサンプル。
AWS サービス説明テキストをファイルリソースとして公開する。
"""

# 処理の流れ:
# 1. Prompt と Resource を FastMCP に登録し、host 側へ一覧提供できるようにする。
# 2. Resource 関数では resources 配下のテキストファイルを読み込み、そのまま返す。
# 3. host はここで返した本文を会話コンテキストへ差し込んで利用する。

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MCP Server Example")


@mcp.prompt(title="Translation")
def translation(lang: str) -> str:
    """翻訳用の指示文テンプレートを返す Prompt。"""

    print("translation")
    return f"以下の文章を{lang}に訳してください。"


@mcp.resource("file://bedrock.txt", name="Bedrock")
def get_bedrock() -> str:
    """Bedrock の説明テキストを Resource として返す。"""

    # resources 配下の説明ファイルを読み込んで返却する。
    with open(
        "resources/bedrock.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.resource("file://s3.txt", name="S3")
def get_s3() -> str:
    """S3 の説明テキストを Resource として返す。"""

    with open(
        "resources/s3.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.resource("file://ec2.txt", name="EC2")
def get_ec2() -> str:
    """EC2 の説明テキストを Resource として返す。"""

    with open(
        "resources/ec2.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


if __name__ == "__main__":
    mcp.run()
