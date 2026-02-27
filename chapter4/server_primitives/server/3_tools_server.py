"""
Prompt / Resource / Tool を提供する MCP サーバーのサンプル。
Qiita API からタグ情報を取得するツールを公開し、host から実行可能にする。
"""

# 処理の流れ:
# 1. Prompt / Resource / Tool をまとめて公開し、host 側から選択利用できるようにする。
# 2. Tool では外部 API を呼び出してタグ情報を取得し、JSON 文字列に整形して返す。
# 3. host 側の Agent は必要に応じてこの Tool を呼び出し、追加情報を取り込んで応答する。

import json

import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(name="MCP Server Example")


@mcp.prompt(title="Translation")
def translation(lang: str) -> str:
    """翻訳タスク向けの指示文テンプレートを返す。"""

    print("translation")
    return f"以下の文章を{lang}に訳してください。"


@mcp.prompt(title="Tag Info")
def tag_info(service_name: str) -> str:
    """タグ情報取得ツールの利用を促す指示文テンプレート。"""

    print("tag_info")
    return (
        f"{service_name}に関するタグ情報をget_tag_infoツールを使って取得してください。"
    )


@mcp.resource("file://bedrock.txt", name="Bedrock")
def get_bedrock() -> str:
    """Bedrock の説明文を Resource として公開する。"""

    with open(
        "resources/bedrock.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.resource("file://s3.txt", name="S3")
def get_s3() -> str:
    """S3 の説明文を Resource として公開する。"""

    with open(
        "resources/s3.txt",
        mode="rt",
        encoding="utf-8",
    ) as f:
        text = f.read()
    return text


@mcp.resource("file://ec2.txt", name="EC2")
def get_ec2() -> str:
    """EC2 の説明文を Resource として公開する。"""

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

    # Qiita API からタグ詳細を取得する。
    response = requests.get(f"https://qiita.com/api/v2/tags/{tag}")

    # UTF-8 日本語を維持するため ensure_ascii=False で整形する。
    return json.dumps(response.json(), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
