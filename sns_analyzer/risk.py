"""
炎上リスクスコア計算モジュール
ネガティブ感情の増加速度・強度・インフルエンサー影響力から炎上リスクを数値化する。
"""

import math


def calculate_viral_risk(analyzed_tweets: list[dict]) -> dict:
    """
    炎上リスクを0〜100で計算して返す。

    スコア内訳:
    - 40%: ネガティブ率
    - 25%: 増加速度（後半 vs 前半）
    - 20%: 怒り・嫌悪の感情強度
    - 15%: ネガティブ発信者のインフルエンス影響
    """
    if not analyzed_tweets:
        return {"score": 0, "level": "low", "alert": False, "reason": "データなし", "neg_rate": 0, "velocity": 0.0}

    total = len(analyzed_tweets)
    negatives = [t for t in analyzed_tweets if t.get("sentiment", {}).get("label") == "negative"]
    neg_rate = len(negatives) / total

    # 感情強度（怒り + 嫌悪）
    emotion_scores = []
    for t in negatives:
        emotions = t.get("sentiment", {}).get("emotions", {})
        anger = emotions.get("anger", 0)
        disgust = emotions.get("disgust", 0)
        emotion_scores.append((anger + disgust) / 2)
    avg_emotion = (sum(emotion_scores) / len(emotion_scores) / 100) if emotion_scores else 0.0

    # 増加速度（後半ネガティブ率 - 前半ネガティブ率）
    sorted_tweets = sorted(analyzed_tweets, key=lambda x: x.get("created_at", ""))
    velocity = 0.0
    if len(sorted_tweets) >= 4:
        half = len(sorted_tweets) // 2
        first_neg = sum(1 for t in sorted_tweets[:half] if t.get("sentiment", {}).get("label") == "negative") / half
        second_neg = sum(1 for t in sorted_tweets[half:] if t.get("sentiment", {}).get("label") == "negative") / (total - half)
        velocity = max(0.0, second_neg - first_neg)

    # インフルエンス影響
    influence_sum = 0.0
    for t in negatives:
        followers = t.get("follower_count", 100)
        likes = t.get("likes_count", 0)
        retweets = t.get("retweet_count", 0)
        engagement = likes + retweets * 2
        influence_sum += math.log10(max(followers, 10)) + math.log10(max(engagement + 1, 1))
    avg_influence_norm = min(1.0, (influence_sum / max(len(negatives), 1)) / 10)

    score = int(min(100, (
        neg_rate * 40 +
        velocity * 25 +
        avg_emotion * 20 +
        avg_influence_norm * 15
    )))

    if score >= 70:
        level = "critical"
        alert = True
    elif score >= 40:
        level = "warning"
        alert = True
    else:
        level = "low"
        alert = False

    reasons = []
    if neg_rate > 0.5:
        reasons.append(f"ネガティブ投稿が{int(neg_rate * 100)}%と高水準")
    if velocity > 0.2:
        reasons.append("ネガティブ投稿が急増傾向")
    if avg_emotion > 0.5:
        reasons.append("怒り・嫌悪の感情が強い")
    if avg_influence_norm > 0.5:
        reasons.append("影響力の高いアカウントが発信")
    reason = "、".join(reasons) if reasons else "現時点でリスクは低い"

    return {
        "score": score,
        "level": level,
        "alert": alert,
        "reason": reason,
        "neg_rate": int(neg_rate * 100),
        "velocity": round(velocity, 3),
    }
