"""
トレンド予測モジュール
過去ツイートのキーワード頻度と感情変化からバズりそうなトピックを予測する。
"""

import json
import re
import math
import anthropic
from collections import Counter


def extract_keywords(tweets: list[dict]) -> list[tuple]:
    """ツイートからハッシュタグ・頻出語を抽出してカウント"""
    words = []
    for tweet in tweets:
        hashtags = re.findall(r'#(\w+)', tweet.get("text", ""))
        words.extend(hashtags)
        tokens = re.findall(r'[ぁ-んァ-ン一-龥a-zA-Z]{2,}', tweet.get("text", ""))
        words.extend(tokens)

    stop = {"する", "ある", "いる", "なる", "れる", "られ", "ため", "こと", "もの",
            "AI", "ai", "the", "and", "or", "is", "it", "to", "of", "a"}
    filtered = [w for w in words if w not in stop]
    return Counter(filtered).most_common(20)


def _calc_velocity(analyzed_tweets: list[dict]) -> float:
    """後半のネガティブ率 - 前半のネガティブ率（速度）"""
    sorted_tweets = sorted(analyzed_tweets, key=lambda x: x.get("created_at", ""))
    if len(sorted_tweets) < 4:
        return 0.0
    half = len(sorted_tweets) // 2
    first = sorted_tweets[:half]
    second = sorted_tweets[half:]
    first_neg = sum(1 for t in first if t.get("sentiment", {}).get("label") == "negative") / len(first)
    second_neg = sum(1 for t in second if t.get("sentiment", {}).get("label") == "negative") / len(second)
    return round(second_neg - first_neg, 3)


def predict_trends(client, analyzed_tweets: list[dict], keyword: str) -> dict:
    """
    Claudeにトレンド予測を依頼する。
    戻り値: {"trending_keywords": list, "momentum": str, "prediction": str, "peak_time": str}
    """
    top_keywords = extract_keywords(analyzed_tweets)
    keywords_text = ", ".join([f"{w}({c}回)" for w, c in top_keywords[:15]])
    velocity = _calc_velocity(analyzed_tweets)

    total = len(analyzed_tweets)
    neg_count = sum(1 for t in analyzed_tweets if t.get("sentiment", {}).get("label") == "negative")
    pos_count = sum(1 for t in analyzed_tweets if t.get("sentiment", {}).get("label") == "positive")

    prompt = f"""以下のSNSデータを分析してトレンド予測をしてください。

キーワード: {keyword}
ツイート数: {total}
ポジティブ: {pos_count}件, ネガティブ: {neg_count}件
頻出語: {keywords_text}
ネガティブ増加速度: {velocity:+.3f}（正=増加、負=減少）

以下のJSON形式のみで回答してください:
{{
  "trending_keywords": ["今後バズりそうなキーワード1", "キーワード2", "キーワード3"],
  "momentum": "rising" | "stable" | "falling",
  "prediction": "今後2〜3時間の予測を1〜2文で日本語で説明",
  "peak_time": "ピーク時間帯の予測（例: 18〜20時）",
  "alert_keyword": "特に注目すべき1語（なければnull）"
}}"""

    if client is None:
        momentum = "rising" if velocity > 0.1 else ("falling" if velocity < -0.1 else "stable")
        return {
            "trending_keywords": [kw for kw, _ in top_keywords[:3]],
            "momentum": momentum,
            "prediction": "（モックモード）ルールベースによる簡易予測です。Claude APIを設定すると詳細な予測が得られます。",
            "peak_time": "18〜22時（推定）",
            "alert_keyword": top_keywords[0][0] if top_keywords else None,
        }

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        raw = match.group()
    try:
        result = json.loads(raw)
        result.setdefault("trending_keywords", [kw for kw, _ in top_keywords[:3]])
        result.setdefault("momentum", "stable")
        result.setdefault("prediction", "データ不足のため予測できません")
        result.setdefault("peak_time", "不明")
        result.setdefault("alert_keyword", None)
        return result
    except (json.JSONDecodeError, ValueError):
        return {
            "trending_keywords": [kw for kw, _ in top_keywords[:3]],
            "momentum": "stable",
            "prediction": "解析に失敗しました",
            "peak_time": "不明",
            "alert_keyword": None,
        }
