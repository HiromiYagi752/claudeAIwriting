"""
Claude によるセンチメント分析モジュール
"""

import json
import re
import anthropic

SYSTEM_PROMPT = """あなたはSNS投稿のセンチメント分析の専門家です。
与えられたツイートを分析し、必ず以下のJSON形式のみで回答してください。

{
  "label": "positive" | "negative" | "neutral",
  "score": 0から100の整数（positiveに近いほど高い）,
  "reason": "判定理由を日本語で1〜2文で説明"
}

JSONのみを返し、前後に説明文や```は不要です。"""


def analyze_tweet(client: anthropic.Anthropic, tweet_text: str) -> dict:
    """
    1件のツイートをClaudeで分析してセンチメント結果を返す。
    戻り値: {"label": str, "score": int, "reason": str}
    """
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"以下のツイートを分析してください:\n\n{tweet_text}"}
        ],
    )

    raw = message.content[0].text.strip()

    # マークダウンコードブロックを除去 (```json ... ``` など)
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group()

    try:
        result = json.loads(raw)
        # 必須フィールドの検証
        label = result.get("label", "neutral")
        if label not in ("positive", "negative", "neutral"):
            label = "neutral"
        score = int(result.get("score", 50))
        score = max(0, min(100, score))
        reason = result.get("reason", "")
        return {"label": label, "score": score, "reason": reason}
    except (json.JSONDecodeError, ValueError):
        return {"label": "neutral", "score": 50, "reason": "解析に失敗しました"}


def analyze_tweets(client: anthropic.Anthropic, tweets: list[dict]) -> list[dict]:
    """
    複数ツイートを分析して結果を付与して返す。
    各要素に sentiment キーが追加される。
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
        return {"total": 0, "positive": 0, "negative": 0, "neutral": 0,
                "positive_pct": 0, "negative_pct": 0, "neutral_pct": 0,
                "avg_score": 0}

    counts = {"positive": 0, "negative": 0, "neutral": 0}
    score_sum = 0

    for t in analyzed_tweets:
        label = t["sentiment"]["label"]
        counts[label] = counts.get(label, 0) + 1
        score_sum += t["sentiment"]["score"]

    avg_score = round(score_sum / total)

    return {
        "total": total,
        "positive": counts["positive"],
        "negative": counts["negative"],
        "neutral": counts["neutral"],
        "positive_pct": round(counts["positive"] / total * 100),
        "negative_pct": round(counts["negative"] / total * 100),
        "neutral_pct": round(counts["neutral"] / total * 100),
        "avg_score": avg_score,
    }
