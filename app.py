"""
AIコンテンツ監査ツール — Webアプリ版
起動: python app.py
ブラウザで http://localhost:5000 にアクセス
"""

import os
import time
import anthropic
from flask import Flask, render_template, request, Response

from audit import (
    audit_url,
    generate_html_report,
    OUTPUT_DIR,
    RATE_LIMIT_DELAY,
)

app = Flask(__name__)


def get_client():
    """Anthropicクライアントを返す。APIキー未設定時はNoneを返す。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


@app.route("/")
def index():
    api_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    return render_template("index.html", api_ok=api_ok)


@app.route("/analyze", methods=["POST"])
def analyze():
    raw = request.form.get("urls", "")
    urls = [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("#")]

    if not urls:
        return render_template("index.html", api_ok=True, error="URLを1つ以上入力してください。")

    client = get_client()
    if client is None:
        return render_template("index.html", api_ok=False, error="ANTHROPIC_API_KEY が設定されていません。")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, "report.html")

    results = []
    for idx, url in enumerate(urls, 1):
        result = audit_url(client, url, idx, len(urls))
        results.append(result)
        if idx < len(urls):
            time.sleep(RATE_LIMIT_DELAY)

    generate_html_report(results, output_path)

    with open(output_path, encoding="utf-8") as f:
        report_html = f.read()

    return Response(report_html, mimetype="text/html")


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
