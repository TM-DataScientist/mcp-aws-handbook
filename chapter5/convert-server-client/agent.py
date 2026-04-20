import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import boto3
from mcp_proxy_for_aws.client import aws_iam_streamablehttp_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# This client fetches the latest report from DynamoDB directly and then sends
# only the conversion step to the remote AgentCore runtime.

# AgentCore Runtime ARN
AGENTCORE_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-west-2:927852416082:runtime/convert_server-61bFlsDJcL"
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
TABLE_NAME = "tech-report"
OUTPUT_URL_PATH = Path(__file__).with_name("latest_download_url.txt")

def create_aws_iam_streamable_http_mcp_client(
    url: str,
    aws_service: str = "bedrock-agentcore"
) -> MCPClient:
    """MCP Proxy for AWSを利用したMCPクライアントを作成する関数"""
    # Used for remote AgentCore runtime endpoint with SigV4/IAM auth.
    streamable_http_mcp_client = MCPClient(
        lambda: aws_iam_streamablehttp_client(
            endpoint=url,
            aws_service=aws_service,
            aws_region="us-west-2", 
            terminate_on_close=False,
        )
    )
    return streamable_http_mcp_client

def get_mcp_endpoint() -> str:
    # Agent runtime ARN must be URL-encoded when embedded in REST path.
    encoded_arn = AGENTCORE_RUNTIME_ARN.replace(":", "%3A").replace("/", "%2F")
    return f"https://bedrock-agentcore.us-west-2.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

def _parse_report_date(value: str) -> datetime:
    """DynamoDB上の日付文字列をdatetimeへ変換する。"""
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"未対応の日付形式です: {value}")


def get_latest_report() -> Dict[str, Any]:
    """tech-reportテーブルから最新のレポートを1件取得する。"""
    table = boto3.resource("dynamodb", region_name=AWS_REGION).Table(TABLE_NAME)
    response = table.scan(
        ProjectionExpression="#id, #date, report",
        ExpressionAttributeNames={"#id": "id", "#date": "date"},
    )
    items = response.get("Items", [])
    if not items:
        raise ValueError(f"DynamoDBテーブル {TABLE_NAME} にレポートがありません")

    report_items = [item for item in items if item.get("report") and item.get("date")]
    if not report_items:
        raise ValueError(f"DynamoDBテーブル {TABLE_NAME} に変換可能なレポートがありません")

    return max(
        report_items,
        key=lambda item: (_parse_report_date(item["date"]), item.get("id", "")),
    )


def build_conversion_prompt(report: Dict[str, Any]) -> str:
    """取得したレポート本文だけを変換ツールに渡すための指示を組み立てる。"""
    return f"""
以下の技術レポート本文をPowerPoint形式に変換してください。
必ず `convert_to_pptx` ツールを1回だけ使ってください。
変換が完了したら、前置きなしでダウンロードURLだけを返してください。

レポートID: {report["id"]}
レポート日付: {report["date"]}

<report>
{report["report"]}
</report>
"""

def extract_download_url(result_text: str) -> str:
    """Agentの応答からダウンロードURLを抽出する。"""
    match = re.search(r"https?://\S+", result_text)
    if not match:
        raise ValueError("変換結果からダウンロードURLを抽出できませんでした")
    return match.group(0)


def main():
    latest_report = get_latest_report()

    # Build AgentCore MCP connection for the conversion step.
    mcp_endpoint = get_mcp_endpoint()
    gateway_server_client = create_aws_iam_streamable_http_mcp_client(mcp_endpoint)

    with gateway_server_client:
        tools = gateway_server_client.list_tools_sync()
        model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
        agent = Agent(
            model=model,
            tools=tools,
        )
        result = agent(build_conversion_prompt(latest_report))
        download_url = extract_download_url(str(result))
        OUTPUT_URL_PATH.write_text(download_url + "\n", encoding="utf-8")
        print(download_url)
        print(f"saved: {OUTPUT_URL_PATH}")

if __name__ == "__main__":
    main()
