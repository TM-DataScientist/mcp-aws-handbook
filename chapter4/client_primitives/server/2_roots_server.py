"""
Sampling と Roots を使う MCP サーバーのサンプル。
翻訳結果を host から受け取った作業ディレクトリ配下のファイルへ保存する。
"""

# 処理の流れ:
# 1. Sampling で翻訳結果を生成し、host から受け取る Roots 情報を保存先に使う。
# 2. 出力先は Roots 配下の output.txt を既定値として組み立てる。
# 3. 同名ファイルがなければ保存し、結果メッセージと本文を host へ返す。

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

mcp = FastMCP(name="Client features sample")


@mcp.tool()
async def translate(language: str, content: str, ctx: Context) -> dict:
    """入力文章を翻訳し、Roots で受け取った場所へ保存する。

    Args:
        language: 翻訳先の言語名（日本語、英語など）
        content: 翻訳対象の原文
    """

    # まず Sampling で翻訳本文を生成する。
    sampling_result = await ctx.session.create_message(
        system_prompt="あなたは優秀な翻訳家です。翻訳結果だけを回答してください。",
        messages=[
            SamplingMessage(
                role="user",
                content=TextContent(
                    type="text",
                    text=f"次の文章を{language}に翻訳してください。\n{content}",
                ),
            ),
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    # host 側が公開する roots から出力先ディレクトリを受け取る。
    list_roots = await ctx.session.list_roots()
    roots = list_roots.roots[0]

    # デフォルトの出力ファイル名を決める。
    filename = "output.txt"
    output_file = Path(roots.uri.path) / filename

    # 既存ファイルがなければ翻訳結果を書き込む。
    if output_file and not output_file.exists():
        with open(output_file, mode="wt", encoding="utf-8") as f:
            f.write(sampling_result.content.text)

        return {
            "message": f"翻訳結果を{output_file.name}に出力しました。",
            "content": sampling_result.content.text,
        }

    else:
        # 既存ファイル保護のため、上書きせずに中止する。
        return {
            "message": "ファイルへの出力を中止しました。",
            "content": sampling_result.content.text,
        }


if __name__ == "__main__":
    mcp.run()
