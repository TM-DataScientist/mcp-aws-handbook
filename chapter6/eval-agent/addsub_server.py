from mcp.server.fastmcp import FastMCP

# Lightweight MCP tool server that exposes addition/subtraction primitives.

# FastMCP サーバーを初期化
mcp = FastMCP("AddSubServer")


@mcp.tool()
def add(a: int, b: int) -> int:
    """
    2つの整数を足し算して結果を返す
    Args:
        a: 第1の整数
        b: 第2の整数
    """
    # Pure function by design, so it is safe to call repeatedly in evaluation.
    return a + b


@mcp.tool()
def sub(a: int, b: int) -> int:
    """
    第1の整数から第2の整数を引き算して結果を返す
    Args:
        a: 第1の整数
        b: 第2の整数
    """
    # No side effects; result only depends on inputs.
    return a - b


def main():
    """サーバーを実行"""
    # Keep default stdio transport for local MCP integration.
    mcp.run()


if __name__ == "__main__":
    main()
