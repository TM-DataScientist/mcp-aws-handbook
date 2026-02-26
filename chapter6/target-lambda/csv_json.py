import csv
import json
from io import StringIO
from typing import Dict, List, Any

# Lambda utility module used behind AgentCore Gateway tools.
# It provides two converters and dispatches by tool name in lambda_handler.

def csv_to_json(csv_string: str) -> List[Dict[str, Any]]:
    """CSV文字列を辞書のリストに変換"""
    try:
        # DictReader maps header row to each subsequent row.
        reader = csv.DictReader(StringIO(csv_string))
        result = [row for row in reader]
        return result
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def json_to_csv(json_list: List[Dict[str, Any]]) -> str:
    """辞書のリストをCSV文字列に変換"""
    try:
        # Empty payloads are rejected to avoid generating header-only CSV silently.
        if not isinstance(json_list, list) or len(json_list) == 0:
            print("❌ Error: リストが空です")
            return ""
       
        # すべての列を抽出
        headers = list(set(
            key for item in json_list if isinstance(item, dict)
            for key in item.keys()
        ))
       
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()
        # Writer handles missing keys in each row by inserting blanks.
        writer.writerows(json_list)
       
        return output.getvalue()
   
    except Exception as e:
        print(f"❌ Error: {e}")
        return ""

def lambda_handler(event, context):
    """エントリポイント"""
    # AgentCore Gatewayから受け取ったツール名を取得
    tool_name = context.client_context.custom['bedrockAgentCoreToolName']
   
    # ターゲット名を取り除きツール名のみ取得
    delimiter = "___"
    print(event)
    if delimiter in tool_name:
        tool_name = tool_name[tool_name.index(delimiter) + len(delimiter):]

    # ツール名に応じて処理を分岐
    if tool_name == "csv_to_json":
        # Tool contract: expect `csv_string` and return JSON string in body.
        csv_data = event.get('csv_string', '')
        result = csv_to_json(csv_data)
        return {'statusCode': 200, 'body': json.dumps(result)}
    elif tool_name == "json_to_csv":
        # Tool contract: expect `json_list` and return raw CSV text in body.
        json_data = event.get('json_list', [])
        result = json_to_csv(json_data)
        return {'statusCode': 200, 'body': result}
    else:
        return {'statusCode': 400, 'body': "ツール名称が不正です"}
