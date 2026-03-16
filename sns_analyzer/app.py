"""
SNS センチメント分析ツール — Webアプリ版
起動: python app.py
ブラウザで http://localhost:5001 にアクセス
"""

import os
import anthropic
from flask import Flask, render_template, request, jsonify

from twitter import search_tweets, is_using_mock
from sentiment import analyze_tweets, summarize

app = Flask(__name__)


def get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


@app.route("/")
def index():
    api_ok = bool(os.environ.get("ANTHROPIC_API_KEY"))
    mock_mode = is_using_mock()
    return render_template("index.html", api_ok=api_ok, mock_mode=mock_mode)


@app.route("/analyze", methods=["POST"])
def analyze():
    keyword = request.form.get("keyword", "").strip()
    max_results = int(request.form.get("max_results", 10))

    if not keyword:
        return jsonify({"error": "キーワードを入力してください"}), 400

    client = get_anthropic_client()
    if client is None:
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません"}), 500

    # ツイート取得
    tweets = search_tweets(keyword, max_results=max_results)
    if not tweets:
        return jsonify({"error": "ツイートが見つかりませんでした"}), 404

    # センチメント分析
    analyzed = analyze_tweets(client, tweets)
    summary = summarize(analyzed)

    # 時系列データ（時間帯別カウント）
    hourly = {}
    for t in analyzed:
        hour = t["created_at"][11:13] if len(t["created_at"]) >= 13 else "00"
        label = t["sentiment"]["label"]
        if hour not in hourly:
            hourly[hour] = {"positive": 0, "negative": 0, "neutral": 0}
        hourly[hour][label] += 1

    hourly_sorted = sorted(hourly.items())
    timeline = {
        "labels": [f"{h}時" for h, _ in hourly_sorted],
        "positive": [v["positive"] for _, v in hourly_sorted],
        "negative": [v["negative"] for _, v in hourly_sorted],
        "neutral": [v["neutral"] for _, v in hourly_sorted],
    }

    return jsonify({
        "keyword": keyword,
        "mock_mode": is_using_mock(),
        "summary": summary,
        "timeline": timeline,
        "tweets": [
            {
                "text": t["text"],
                "author": t["author"],
                "created_at": t["created_at"],
                "label": t["sentiment"]["label"],
                "score": t["sentiment"]["score"],
                "reason": t["sentiment"]["reason"],
            }
            for t in analyzed
        ],
    })


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
