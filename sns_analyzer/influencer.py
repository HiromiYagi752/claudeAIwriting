"""
インフルエンサー特定モジュール
フォロワー数・エンゲージメントから影響力スコアを算出し上位ユーザーを返す。
"""

import math


def calculate_influence_score(tweet: dict) -> float:
    """
    フォロワー数・いいね・RTからインフルエンス スコア（0〜100）を計算。
    スコア = エンゲージメント率 × 0.4 + リーチスコア × 0.6
    """
    followers = tweet.get("follower_count", 0)
    likes = tweet.get("likes_count", 0)
    retweets = tweet.get("retweet_count", 0)

    engagement = likes + retweets * 2
    engagement_rate = (engagement / max(followers, 1)) * 100
    reach_score = math.log10(max(followers, 10)) * 20

    score = min(100, engagement_rate * 0.4 + reach_score * 0.6)
    return round(score, 1)


def identify_influencers(analyzed_tweets: list[dict]) -> list[dict]:
    """
    分析済みツイートからインフルエンサーを特定してトップ5を返す。
    戻り値リストの各要素: author, influence_score, sentiment_label, follower_count, likes_count, retweet_count, text
    """
    results = []
    for tweet in analyzed_tweets:
        score = calculate_influence_score(tweet)
        results.append({
            "author": tweet.get("author", "unknown"),
            "text": tweet.get("text", ""),
            "follower_count": tweet.get("follower_count", 0),
            "likes_count": tweet.get("likes_count", 0),
            "retweet_count": tweet.get("retweet_count", 0),
            "influence_score": score,
            "sentiment_label": tweet.get("sentiment", {}).get("label", "neutral"),
            "sentiment_score": tweet.get("sentiment", {}).get("score", 50),
        })

    results.sort(key=lambda x: x["influence_score"], reverse=True)
    return results[:5]
