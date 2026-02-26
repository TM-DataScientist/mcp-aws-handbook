import asyncio
import boto3
import os
import tempfile
from datetime import datetime
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Pipeline summary:
# user text -> Bedrock prompt conversion (Marp markdown) -> marp CLI -> pptx
# -> S3 upload -> presigned URL response.

# MCPサーバーの初期化
mcp = FastMCP("ConvertServer", host="0.0.0.0", stateless_http=True)

# システムプロンプト
SYSTEM_PROMPT = """
あなたの責務は入力テキストをMarpフォーマットに変換することです。
入力テキストの構成を考慮して、プレゼンファイルを生成するためのMarpフォーマットに正確に変換してください。


Marpフォーマットでは以下ルールを厳守してください
- スライドの区切りは"---"で設定してください
- 入力テキストの構成を考慮して適切な見出しを設定してください
- 見出しは"#", "##", "###"で表現してください
- 1つのトピックを、1つのスライドにまとめてください
- <header></header>内のテキストをファイル先頭としてください。これ以前にはメタデータ含め一切のテキストを含めないでください。
<header>
---
marp: true
theme: default
paginate: true
---
</header>
"""
def _convert_to_marp_format(text: str = Field(description="Marpフォーマットに変換するテキスト")) -> str:
    """入力テキストをMarpフォーマットに変換する"""
    # This function is intentionally synchronous because Bedrock converse call
    # is blocking and returns the full converted markdown in one response.
    # AWSセッションの作成（デフォルトプロファイルを使用）
    session = boto3.Session()
    client = session.client("bedrock-runtime")
   
    # Claudeモデルに変換を依頼
    response = client.converse(
        modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        messages=[{
            "role": "user",
            "content": [{
                "text": f"<入力>{text}</入力>"
            }]
        }],
        system=[{"text": SYSTEM_PROMPT}]
    )
   
    return response["output"]["message"]["content"][0]["text"]

MARP_PATH = "marp"  # Marpコマンドのパス
async def _process_marp(input_file_path: str, output_file_path: str) -> Dict[str, Any]:
    """Marpコマンドを実行してMarkdownファイルをpptxに変換する。"""
    # marp CLI is executed as a child process to keep this server non-blocking.
    # Marpプロセスを非同期で実行
    process = await asyncio.create_subprocess_exec(
        MARP_PATH,
        input_file_path,
        "--output", output_file_path,
        "--theme", "default",
        "--pptx-editable",  # 編集可能なpptxを生成
        "--allow-local-files",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
   
    # プロセスの完了を待機（タイムアウト60秒）
    stdout, stderr = await asyncio.wait_for(
        process.communicate(),
        timeout=60
    )
   
    return {
        "returncode": process.returncode,
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "success": process.returncode == 0
    }

def _upload_to_s3(file_name: str, bucket_name: str, key: str) -> str:
    """ファイルをS3にアップロードし、署名付きURLを生成する。"""
    # The returned presigned URL is used by clients to download without
    # exposing bucket objects publicly.
    # AWSセッションの作成
    session = boto3.Session()
    client = session.client("s3")
   
    # ファイルをS3にアップロード
    client.upload_file(file_name, bucket_name, key)
   
    # 署名付きURLを生成（1時間有効）
    response = client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": key},
        ExpiresIn=3600,
        HttpMethod="GET"
    )
   
    return response

BUCKET = "<S3バケット名>"  # S3バケット名 : slide-data-<AWSアカウントID>" 
TEMP_DIR_PATH = tempfile.gettempdir()
TEMP_FILE_PATH = "report_tmp.md"  # 一時ファイルのパス

@mcp.tool()
async def convert_to_pptx(text: str = Field(description="pptxに変換するテキスト")) -> str:
    """
    入力テキストをPowerPointプレゼンテーション（pptx）に変換する。
   
    処理フロー:
    1. テキストをMarp形式に変換（Claude使用）
    2. Marp形式のテキストを一時ファイルに保存
    3. Marpコマンドでpptxファイルを生成
    4. 生成されたファイルをS3にアップロード
    5. ダウンロード可能な署名付きURLを返却
   
    Args:
        text: 変換対象のテキスト
       
    Returns:
        生成されたpptxファイルのダウンロードURL
    """
    # タイムスタンプ付きの出力ファイル名を生成
    output_file_path = datetime.now().strftime("%Y%m%d_%H%M%S") + ".pptx"
   
    # Step 1: call Bedrock to generate valid Marp markdown from free-form text.
    # テキストをMarp形式に変換
    marp_text = _convert_to_marp_format(text)
   
    # Step 2: persist markdown so marp CLI can read it as an input file.
    # Marp形式のテキストを一時ファイルに保存 
    with open(os.path.join(TEMP_DIR_PATH, TEMP_FILE_PATH), "w", encoding="utf-8") as f:
        f.write(marp_text)
   
    # Step 3: run marp CLI and generate the final editable pptx file.
    # Marpでpptxファイルを生成
    await _process_marp(os.path.join(TEMP_DIR_PATH, TEMP_FILE_PATH), os.path.join(TEMP_DIR_PATH, output_file_path))
   
    # Step 4/5: upload and return a presigned URL so caller can download.
    # 生成されたファイルをS3にアップロードし、URLを取得
    url = _upload_to_s3(os.path.join(TEMP_DIR_PATH, output_file_path), BUCKET, output_file_path)
   
    return url

if __name__ == "__main__":
    # MCPサーバーを起動（HTTP transport使用）
    mcp.run(transport="streamable-http")
