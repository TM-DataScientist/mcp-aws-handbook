"""
Sampling / Roots / Elicitation を使う MCP サーバーのサンプル。
出力先ファイルが既にある場合、host に新しいファイル名を問い合わせる。
"""

from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent
from pydantic import BaseModel, Field

mcp = FastMCP(name="Client features sample")


class RenameRequest(BaseModel):
    """重複時に host へ問い合わせるファイル名スキーマ。"""

    filename: str = Field(description="filename")


@mcp.tool()
async def translate(language: str, content: str, ctx: Context) -> dict:
    """入力文章を翻訳し、必要なら Elicitation で保存名を確認する。

    Args:
        language: 翻訳先の言語名（日本語、英語など）
        content: 翻訳対象の原文
    """

    # Sampling で翻訳結果を生成する。
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

    # host 側 roots から書き込み先ディレクトリを取得する。
    list_roots = await ctx.session.list_roots()
    roots = list_roots.roots[0]

    # まずは既定名 output.txt で保存を試みる。
    filename = "output.txt"
    output_file = Path(roots.uri.path) / filename

    # 未作成ならそのまま保存して終了。
    if output_file and not output_file.exists():
        with open(output_file, mode="wt", encoding="utf-8") as f:
            f.write(sampling_result.content.text)

        return {
            "message": f"翻訳結果を{output_file.name}に出力しました。",
            "content": sampling_result.content.text,
        }

    else:
        # 既に存在する場合は host に別名入力を依頼する。
        elicit_result = await ctx.elicit(
            message=(f"{filename}がすでに存在します。別名を指定してください。"),
            schema=RenameRequest,
        )

        # ユーザーが受け入れて値を返した場合のみ再保存する。
        if elicit_result.action == "accept" and elicit_result.data:
            filename = elicit_result.data.filename
            output_file = Path(roots.uri.path) / filename

            with open(output_file, mode="wt", encoding="utf-8") as f:
                f.write(sampling_result.content.text)

            return {
                "message": f"翻訳結果を{output_file.name}に出力しました。",
                "content": sampling_result.content.text,
            }


if __name__ == "__main__":
    mcp.run()
