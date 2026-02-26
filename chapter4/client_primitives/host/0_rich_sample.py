"""
Rich の基本表示を確認するサンプル。
文字装飾・パネル表示・対話入力の最小例をまとめている。
"""

from rich import print
from rich.panel import Panel
from rich.prompt import Prompt

# 1) 通常の print と同様に文字列を表示する。
print("こんにちは")  # Richライブラリのprint関数が呼び出される

# 2) マークアップで色を指定して表示する。
print("[cyan]青色のテキスト[/cyan]")
print("[yellow]黄色のテキスト[/yellow]")
print("[dim]薄い色のテキスト[/dim]")

# 3) 太字・下線などの装飾もタグで指定できる。
print("[bold]太字[/bold]")
print("[underline]下線[/underline]")
print("[bold blue]太字の青色[/bold blue]")

# 4) Panel を使うと枠付きで情報を見やすく表示できる。
print(Panel("こんにちは", title="タイトル"))

print(Panel("[cyan]装飾も可能[/cyan]", title="[yellow]タイトル[/yellow]"))

# 5) Prompt でユーザー入力を受け取り、結果を表示する。
value = Prompt.ask("[yellow]text[/yellow]")

print(f"入力した値は[bold blue]{value}[/bold blue]です。")
