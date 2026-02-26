"""
streamable-http で公開する MCP サーバーのサンプル。
Prompt / Resource / Tool を HTTP 経由で提供し、Web 接続の host から利用させる。
"""

import json

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MCP Server Example")


@mcp.prompt(title="Translation")
def translation(lang: str) -> str:
    """翻訳タスク用の指示文テンプレートを返す。"""

    print("translation")
    return f"以下の文章を{lang}に訳してください。"


@mcp.prompt(title="Tag Info")
def tag_info(service_name: str) -> str:
    """タグ情報取得ツールの使用を促す Prompt。"""

    print("translation")
    return (
        f"{service_name}に関するタグ情報をget_tag_infoツールを使って取得してください。"
    )


@mcp.resource("file://bedrock.txt", name="Bedrock")
def get_bedrock() -> str:
    """Bedrock 説明ファイルを Resource として返す。"""

    with open(
        "resources/bedrock.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.resource("file://s3.txt", name="S3")
def get_s3() -> str:
    """S3 説明ファイルを Resource として返す。"""

    with open(
        "resources/s3.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.resource("file://ec2.txt", name="EC2")
def get_ec2() -> str:
    """EC2 説明ファイルを Resource として返す。"""

    with open(
        "resources/ec2.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.tool()
async def get_tag_info(tag: str) -> str:
    """Qiitaで登録されているタグの情報を取得します。
    タグに指定可能な値は、Bedrock、EC2、S3のいずれかです。
    """

    # HTTP API でタグ情報を取得する。
    response = requests.get(f"https://qiita.com/api/v2/tags/{tag}")
    response.json()

    # host 側で表示しやすいよう JSON 文字列として整形して返す。
    return json.dumps(response.json(), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # streamable-http トランスポートでサーバーを公開する。
    mcp.run(transport="streamable-http")
