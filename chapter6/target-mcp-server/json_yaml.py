import yaml
from typing import Dict, List, Any
from mcp.server.fastmcp import FastMCP

# Utility MCP server that exposes two conversion tools:
# - json_to_yaml
# - yaml_to_json
# The conversion contract intentionally uses `List[Dict[str, Any]]`.

# MCPサーバー初期化
mcp = FastMCP("JsonYamlConverter", host="0.0.0.0", stateless_http=True)

@mcp.tool()
def json_to_yaml(json_list: List[Dict[str, Any]]) -> str:
    """JSONリストをYAML文字列に変換"""
    try:
        # Validate input shape early to return a predictable empty value on error.
        if not isinstance(json_list, list):
            print("❌ Error: 入力はリスト形式である必要があります")
            return ""
       
        yaml_str = yaml.dump(
            json_list,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False
        )
        return yaml_str
    except Exception as e:
        print(f"❌ エラー: {e}")
        return ""

@mcp.tool()
def yaml_to_json(yaml_string: str) -> List[Dict[str, Any]]:
    """YAML文字列をJSONリストに変換"""
    try:
        # Parse YAML safely (no arbitrary object construction).
        data = yaml.safe_load(yaml_string)
        if isinstance(data, list):
            # リスト内の各要素が辞書であることを確認
            if all(isinstance(item, dict) for item in data):
                return data
            else:
                print("❌ Error: YAMLリスト内のすべてのアイテムは辞書である必要があります")
                return []
        else:
            print("❌ Error: YAMLはリスト形式である必要があります")
            return []
    except yaml.YAMLError as e:
        print(f"❌ Error: 無効なYAML形式です - {e}")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

if __name__ == "__main__":
    # Expose tool endpoints through HTTP-compatible MCP transport.
    mcp.run(transport="streamable-http")
