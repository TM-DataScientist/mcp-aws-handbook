"""Playwright を用いた app_with_kb.py の GUI テストスクリプト"""

import asyncio
import re
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright


CHROMIUM_PATH = str(Path.home() / ".cache/ms-playwright/chromium_headless_shell-1208/chrome-headless-shell-linux64/chrome-headless-shell")
APP_URL = "http://localhost:8502"
TEST_QUERY = "AWS Bedrock API Key について教えて"
OUTPUT_FILE = Path(__file__).parent / "test_result.md"

# 応答が来るまでの最大待機時間 (ms)
RESPONSE_TIMEOUT = 300_000


async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROMIUM_PATH,
            headless=True,
        )
        page = await browser.new_page()

        print(f"[1/5] {APP_URL} に接続中...")
        await page.goto(APP_URL, wait_until="networkidle", timeout=30_000)

        print("[2/5] Streamlit の初期化を待機中...")
        # Streamlit のローディングスピナーが消えるまで待つ
        await page.wait_for_selector(
            '[data-testid="stApp"]', state="visible", timeout=30_000
        )
        # 追加の安定化待機
        await page.wait_for_timeout(3_000)

        print(f"[3/5] 入力フィールドにテスト入力を送信: {TEST_QUERY!r}")
        chat_input = page.locator('[data-testid="stChatInput"] textarea')
        await chat_input.fill(TEST_QUERY)
        await chat_input.press("Enter")

        print("[4/5] 応答を待機中 (最大 5 分)...")
        # スピナー (回答生成中) が出ている間は待つ
        try:
            await page.wait_for_selector(
                '[data-testid="stStatusWidget"]', state="visible", timeout=10_000
            )
            print("  ... スピナーを検知、生成完了まで待機...")
            await page.wait_for_selector(
                '[data-testid="stStatusWidget"]', state="hidden", timeout=RESPONSE_TIMEOUT
            )
        except Exception:
            # スピナーが表示されない場合はそのまま進む
            pass

        # アシスタントメッセージが現れるまで待機
        await page.wait_for_selector(
            '[data-testid="stChatMessageContent"]',
            state="visible",
            timeout=RESPONSE_TIMEOUT,
        )
        # レンダリング完了まで少し待つ
        await page.wait_for_timeout(3_000)

        print("[5/5] 画面のテキストを取得して Markdown に保存...")
        messages = []
        for el in await page.locator('[data-testid="stChatMessage"]').all():
            role_el = el.locator('[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"]')
            # role を判定 (data-testid 属性で区別)
            outer_html = await el.get_attribute("data-testid") or ""

            # メッセージ本文を取得
            content_el = el.locator('[data-testid="stChatMessageContent"]')
            text = (await content_el.inner_text()).strip()

            # ユーザー / アシスタントを class から推定
            class_attr = await el.get_attribute("class") or ""
            if "user" in class_attr.lower():
                role = "user"
            else:
                role = "assistant"
            messages.append((role, text))

        await browser.close()

        # ロールが判定できなかった場合のフォールバック: 最初がユーザー、以降がアシスタント
        if messages and all(r == "assistant" for r, _ in messages):
            fixed = []
            for i, (r, t) in enumerate(messages):
                fixed.append(("user" if i % 2 == 0 else "assistant", t))
            messages = fixed

        # Markdown として保存
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "# RAG チャットアプリ GUI テスト結果",
            "",
            f"- **実行日時**: {now}",
            f"- **テスト URL**: {APP_URL}",
            f"- **テスト入力**: {TEST_QUERY}",
            "",
            "---",
            "",
            "## 会話ログ",
            "",
        ]
        for role, text in messages:
            if role == "user":
                lines.append(f"### ユーザー\n\n{text}\n")
            else:
                lines.append(f"### アシスタント\n\n{text}\n")

        OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n結果を保存しました: {OUTPUT_FILE}")
        print("\n--- 取得テキスト (先頭 500 文字) ---")
        print("\n".join(lines)[:500])


if __name__ == "__main__":
    asyncio.run(run_test())
