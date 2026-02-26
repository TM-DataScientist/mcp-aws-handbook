"""
Sampling を使う MCP サーバーのサンプル。
translate ツール内で host 側のモデル推論を呼び出して翻訳結果を作る。
"""

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import SamplingMessage, TextContent

mcp = FastMCP(name="Client features sample")


@mcp.tool()
async def translate(language: str, content: str, ctx: Context) -> dict:
    """入力文章を指定言語へ翻訳する。

    Args:
        language: 翻訳先の言語名（日本語、英語など）
        content: 翻訳対象の原文
    """

    # サーバーは host に Sampling を依頼し、host 側モデルに推論させる。
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

    # ツール結果として翻訳テキストを返す。
    return {
        "content": sampling_result.content.text,
    }


if __name__ == "__main__":
    mcp.run()
