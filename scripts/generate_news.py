"""
小児医療ニュース 自動生成スクリプト
毎朝 GitHub Actions から実行され、OpenAI API でニュースを取得し
HTML テンプレートに埋め込んで GitHub Pages に公開する。
"""

import os
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from openai import OpenAI

# ── 日付（日本時間） ────────────────────────────────────────────────
JST = timezone(timedelta(hours=9))
today = datetime.now(JST)
weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
date_display = f"{today.year}年{today.month}月{today.day}日（{weekday_ja[today.weekday()]}）"
date_slug = today.strftime("%Y-%m-%d")   # ファイル名用: 2026-05-01
page_url = f"https://sakkyota777.github.io/pediatric-news/{date_slug}.html"

print(f"[INFO] 対象日: {date_display}")

# ── OpenAI API 呼び出し ────────────────────────────────────────────
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

prompt = f"""今日は{date_display}です。
以下の3つのカテゴリについて、ウェブを検索して最新の小児医療ニュースを各1件ずつ要約してください。

① 国際・海外：WHO、CDC、AAP、Lancet、BMJ、NEJM 等の国際機関・医学誌の最新情報
② 日本全体：日本小児科学会、厚生労働省、こども家庭庁等の国内最新情報
③ 地域（北多摩西部）：東京都の立川市・国立市・国分寺市・小平市・東村山市・武蔵村山市・東大和市・清瀬市・東久留米市・西東京市周辺の小児医療・保健情報

必ず以下の JSON 形式のみで回答してください（前後の説明文は不要です）：
{{
  "international": {{
    "source": "情報源名（例：World Health Organization）",
    "topic": "トピック名（簡潔に）",
    "bullets": [
      "概要：〜",
      "ポイント：〜"
    ],
    "takeaway": "臨床的示唆・実務への影響（2〜3文）"
  }},
  "japan": {{
    "source": "情報源名",
    "topic": "トピック名",
    "bullets": [
      "概要：〜",
      "ポイント：〜"
    ],
    "takeaway": "臨床的示唆・実務への影響（2〜3文）"
  }},
  "local": {{
    "source": "情報源名",
    "topic": "トピック名",
    "bullets": [
      "概要：〜",
      "内容：〜"
    ],
    "takeaway": "地域の小児科外来への影響・対応（2〜3文）"
  }}
}}"""

print("[INFO] OpenAI API にニュースを問い合わせ中...")

try:
    response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search_preview"}],
        input=prompt,
    )
    raw_content = response.output_text
    print("[INFO] API レスポンス取得完了")
except Exception as e:
    print(f"[ERROR] OpenAI API 呼び出し失敗: {e}", file=sys.stderr)
    sys.exit(1)

# ── JSON パース ────────────────────────────────────────────────────
def parse_news_json(text: str) -> dict:
    """レスポンスから JSON を抽出してパースする。"""
    # JSON ブロックを抽出（```json ... ``` または { ... } 形式に対応）
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group())
    raise ValueError("JSON が見つかりませんでした")

def fallback_news(label: str) -> dict:
    return {
        "source": "情報取得エラー",
        "topic": f"{label}のニュース取得に失敗しました",
        "bullets": ["本日のシステムエラーにより情報を取得できませんでした。"],
        "takeaway": "明日の配信をお待ちください。",
    }

try:
    news = parse_news_json(raw_content)
    # 必須キーの確認
    for key in ("international", "japan", "local"):
        if key not in news:
            raise KeyError(key)
    print("[INFO] JSON パース成功")
except Exception as e:
    print(f"[WARN] JSON パース失敗（{e}）。フォールバックを使用します。")
    news = {
        "international": fallback_news("国際・海外"),
        "japan":         fallback_news("日本全体"),
        "local":         fallback_news("地域（北多摩西部）"),
    }

# ── HTML 生成 ──────────────────────────────────────────────────────
def bullets_to_html(bullets: list) -> str:
    return "\n              ".join(f"<li>{b}</li>" for b in bullets)

template_path = os.path.join(os.path.dirname(__file__), "..", "template.html")
with open(template_path, encoding="utf-8") as f:
    html = f.read()

replacements = {
    "{{DATE}}":         date_display,
    "{{INT_SOURCE}}":   news["international"]["source"],
    "{{INT_TOPIC}}":    news["international"]["topic"],
    "{{INT_BULLETS}}":  bullets_to_html(news["international"]["bullets"]),
    "{{INT_TAKEAWAY}}": news["international"]["takeaway"],
    "{{JPN_SOURCE}}":   news["japan"]["source"],
    "{{JPN_TOPIC}}":    news["japan"]["topic"],
    "{{JPN_BULLETS}}":  bullets_to_html(news["japan"]["bullets"]),
    "{{JPN_TAKEAWAY}}": news["japan"]["takeaway"],
    "{{LOC_SOURCE}}":   news["local"]["source"],
    "{{LOC_TOPIC}}":    news["local"]["topic"],
    "{{LOC_BULLETS}}":  bullets_to_html(news["local"]["bullets"]),
    "{{LOC_TAKEAWAY}}": news["local"]["takeaway"],
}

for placeholder, value in replacements.items():
    html = html.replace(placeholder, value)

# ── ファイル保存 ───────────────────────────────────────────────────
repo_root = os.path.join(os.path.dirname(__file__), "..")

daily_path = os.path.join(repo_root, f"{date_slug}.html")
index_path  = os.path.join(repo_root, "index.html")

with open(daily_path, "w", encoding="utf-8") as f:
    f.write(html)
with open(index_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"[INFO] 保存完了: {date_slug}.html, index.html")

# ── GitHub Actions への出力 ────────────────────────────────────────
# GITHUB_OUTPUT 環境変数が設定されている場合のみ書き込む
github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"date={date_display}\n")
        f.write(f"url={page_url}\n")
    print(f"[INFO] GitHub Actions outputs 設定完了")

print(f"[INFO] 公開 URL: {page_url}")

# ── LINE 送信 ──────────────────────────────────────────────────────
import urllib.request

line_token   = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
line_user_id = os.environ.get("LINE_USER_ID")

if line_token and line_user_id:
    message_text = (
        f"🏥 本日の小児医療ニュース\n"
        f"{date_display}\n\n"
        f"▶ こちらからご覧ください\n"
        f"{page_url}"
    )
    payload = json.dumps({
        "to": line_user_id,
        "messages": [{"type": "text", "text": message_text}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {line_token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as res:
            print(f"[INFO] LINE 送信成功: {res.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"[ERROR] LINE 送信失敗: {e.code} {body}", file=sys.stderr)
        sys.exit(1)
else:
    print("[WARN] LINE_CHANNEL_ACCESS_TOKEN または LINE_USER_ID が未設定のためスキップ")

print("[INFO] 完了")
