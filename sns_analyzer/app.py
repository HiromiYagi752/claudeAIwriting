"""
SNS センチメント分析ツール — Webアプリ版
起動: python app.py
ブラウザで http://localhost:5001 にアクセス
"""

import os
import anthropic
from flask import Flask, render_template, request, jsonify, Response

from twitter import search_tweets, is_using_mock
from sentiment import analyze_tweets, summarize
from trend import predict_trends
from influencer import identify_influencers
from risk import calculate_viral_risk
from report import generate_report

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

    tweets = search_tweets(keyword, max_results=max_results)
    if not tweets:
        return jsonify({"error": "ツイートが見つかりませんでした"}), 404

    analyzed = analyze_tweets(client, tweets)
    summary = summarize(analyzed)

    # 時系列データ
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

    trend = predict_trends(client, analyzed, keyword)
    influencers = identify_influencers(analyzed)
    risk = calculate_viral_risk(analyzed)

    return jsonify({
        "keyword": keyword,
        "mock_mode": is_using_mock(),
        "summary": summary,
        "timeline": timeline,
        "trend": trend,
        "influencers": influencers,
        "risk": risk,
        "tweets": [
            {
                "text": t["text"],
                "author": t["author"],
                "created_at": t["created_at"],
                "follower_count": t.get("follower_count", 0),
                "likes_count": t.get("likes_count", 0),
                "retweet_count": t.get("retweet_count", 0),
                "label": t["sentiment"]["label"],
                "score": t["sentiment"]["score"],
                "emotions": t["sentiment"]["emotions"],
                "reason": t["sentiment"]["reason"],
            }
            for t in analyzed
        ],
    })


@app.route("/compare", methods=["POST"])
def compare():
    """複数キーワードを同時分析して比較データを返す"""
    keywords_raw = request.form.get("keywords", "").strip()
    max_results = int(request.form.get("max_results", 5))

    keywords = [k.strip() for k in keywords_raw.replace("、", ",").split(",") if k.strip()]
    if len(keywords) < 2:
        return jsonify({"error": "比較するキーワードを2つ以上カンマ区切りで入力してください"}), 400
    if len(keywords) > 4:
        keywords = keywords[:4]

    client = get_anthropic_client()
    if client is None:
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません"}), 500

    results = []
    for kw in keywords:
        tweets = search_tweets(kw, max_results=max_results)
        if not tweets:
            results.append({"keyword": kw, "error": "ツイートなし"})
            continue
        analyzed = analyze_tweets(client, tweets)
        s = summarize(analyzed)
        risk = calculate_viral_risk(analyzed)
        results.append({
            "keyword": kw,
            "summary": s,
            "risk": risk,
        })

    return jsonify({"mock_mode": is_using_mock(), "results": results})


@app.route("/report", methods=["POST"])
def report():
    """分析結果からHTMLレポートを生成して返す"""
    keyword = request.form.get("keyword", "").strip()
    max_results = int(request.form.get("max_results", 10))

    if not keyword:
        return jsonify({"error": "キーワードを入力してください"}), 400

    client = get_anthropic_client()
    if client is None:
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません"}), 500

    tweets = search_tweets(keyword, max_results=max_results)
    if not tweets:
        return jsonify({"error": "ツイートが見つかりませんでした"}), 404

    analyzed = analyze_tweets(client, tweets)
    summary = summarize(analyzed)
    trend = predict_trends(client, analyzed, keyword)
    influencers = identify_influencers(analyzed)
    risk = calculate_viral_risk(analyzed)

    html = generate_report(client, keyword, summary, trend, risk, influencers, analyzed)
    return Response(html, mimetype="text/html")


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5001)
