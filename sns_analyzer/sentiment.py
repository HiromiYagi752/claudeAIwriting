"""
Claude によるセンチメント分析モジュール（8感情対応版）
"""

import json
import re
import anthropic

SYSTEM_PROMPT = """あなたはSNS投稿のセンチメント分析の専門家です。
与えられたツイートを分析し、必ず以下のJSON形式のみで回答してください。

{
  "label": "positive" | "negative" | "neutral",
  "score": 0から100の整数（positiveに近いほど高い）,
  "emotions": {
    "joy": 0から100の整数（喜び）,
    "anger": 0から100の整数（怒り）,
    "sadness": 0から100の整数（悲しみ）,
    "surprise": 0から100の整数（驚き）,
    "anxiety": 0から100の整数（不安）,
    "disgust": 0から100の整数（嫌悪）,
    "trust": 0から100の整数（信頼）,
    "anticipation": 0から100の整数（期待）
  },
  "reason": "判定理由を日本語で1〜2文で説明"
}

JSONのみを返し、前後に説明文や```は不要です。"""

EMOTIONS_JA = {
    "joy": "喜び",
    "anger": "怒り",
    "sadness": "悲しみ",
    "surprise": "驚き",
    "anxiety": "不安",
    "disgust": "嫌悪",
    "trust": "信頼",
    "anticipation": "期待",
}

DEFAULT_EMOTIONS = {k: 0 for k in EMOTIONS_JA}


def analyze_tweet(client: anthropic.Anthropic, tweet_text: str) -> dict:
    """
    1件のツイートをClaudeで分析してセンチメント結果を返す。
    戻り値: {"label": str, "score": int, "emotions": dict, "reason": str}
    """
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"以下のツイートを分析してください:\n\n{tweet_text}"}
        ],
    )

    raw = message.content[0].text.strip()

    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group()

    try:
        result = json.loads(raw)
        label = result.get("label", "neutral")
        if label not in ("positive", "negative", "neutral"):
            label = "neutral"
        score = int(result.get("score", 50))
        score = max(0, min(100, score))
        reason = result.get("reason", "")

        raw_emotions = result.get("emotions", {})
        emotions = {}
        for key in EMOTIONS_JA:
            val = int(raw_emotions.get(key, 0))
            emotions[key] = max(0, min(100, val))

        return {"label": label, "score": score, "emotions": emotions, "reason": reason}
    except (json.JSONDecodeError, ValueError):
        return {"label": "neutral", "score": 50, "emotions": DEFAULT_EMOTIONS.copy(), "reason": "解析に失敗しました"}


def analyze_tweets(client: anthropic.Anthropic, tweets: list[dict]) -> list[dict]:
    """
    複数ツイートを分析して結果を付与して返す。
    """
    results = []
    for tweet in tweets:
        sentiment = analyze_tweet(client, tweet["text"])
        results.append({**tweet, "sentiment": sentiment})
    return results


def summarize(analyzed_tweets: list[dict]) -> dict:
    """
    分析済みツイートの集計サマリーを返す。
    """
    total = len(analyzed_tweets)
    if total == 0:
        return {
            "total": 0,
            "positive": 0, "negative": 0, "neutral": 0,
            "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0,
            "avg_score": 0,
            "emotions_avg": DEFAULT_EMOTIONS.copy(),
        }

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    score_sum = 0
    emotions_sum = {k: 0 for k in EMOTIONS_JA}

    for t in analyzed_tweets:
        label = t["sentiment"]["label"]
        counts[label] = counts.get(label, 0) + 1
        score_sum += t["sentiment"]["score"]
        for key in EMOTIONS_JA:
            emotions_sum[key] += t["sentiment"]["emotions"].get(key, 0)

    avg_score = round(score_sum / total)
    emotions_avg = {k: round(v / total) for k, v in emotions_sum.items()}

    return {
        "total": total,
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
        "positive_pct": round(counts["positive"] / total * 100),
        "negative_pct": round(counts["negative"] / total * 100),
        "neutral_pct": round(counts["neutral"] / total * 100),
        "avg_score": avg_score,
        "emotions_avg": emotions_avg,
    }
