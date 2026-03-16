"""
Twitter API v2 クライアント（モックデータ切り替え対応）

環境変数 TWITTER_BEARER_TOKEN が設定されている場合は実APIを使用。
未設定の場合はモックデータを返す。
"""

import os
import random
import datetime
import requests

BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")


MOCK_TWEETS = [
    {"id": "1", "text": "AIの進化が本当にすごい！毎日新しい発見があって楽しい。#AI", "created_at": "2026-03-16T08:00:00Z", "author": "user_a"},
    {"id": "2", "text": "最近のAIツールは使いにくいものが多くて困る。もっとシンプルにしてほしい。#AI", "created_at": "2026-03-16T09:00:00Z", "author": "user_b"},
    {"id": "3", "text": "AIについて勉強中。まだよくわからないけど面白そう。#AI", "created_at": "2026-03-16T10:00:00Z", "author": "user_c"},
    {"id": "4", "text": "AIで業務効率が3倍になった！これは革命だと思う。#AI #生産性", "created_at": "2026-03-16T11:00:00Z", "author": "user_d"},
    {"id": "5", "text": "AIに仕事を奪われそうで不安。将来どうなるんだろう…#AI", "created_at": "2026-03-16T12:00:00Z", "author": "user_e"},
    {"id": "6", "text": "ChatGPTとClaudeを比較してみたけど、どちらも素晴らしいね。#AI", "created_at": "2026-03-16T13:00:00Z", "author": "user_f"},
    {"id": "7", "text": "AIのバイアス問題はまだ解決されていない。もっと議論が必要。#AI", "created_at": "2026-03-16T14:00:00Z", "author": "user_g"},
    {"id": "8", "text": "AIアートが好きすぎる。毎日見てるだけで幸せ。#AI #アート", "created_at": "2026-03-16T15:00:00Z", "author": "user_h"},
    {"id": "9", "text": "AIの規制が遅すぎる。このままでは危険だ。#AI", "created_at": "2026-03-16T16:00:00Z", "author": "user_i"},
    {"id": "10", "text": "AIで作った音楽、なかなか良かった！驚いた。#AI #音楽", "created_at": "2026-03-16T17:00:00Z", "author": "user_j"},
]


def search_tweets(keyword: str, max_results: int = 10) -> list[dict]:
    """
    キーワードでツイートを検索して返す。
    TWITTER_BEARER_TOKEN が設定されていればAPIを、なければモックを使用。
    """
    if BEARER_TOKEN:
        return _search_tweets_api(keyword, max_results)
    else:
        return _search_tweets_mock(keyword, max_results)


def _search_tweets_api(keyword: str, max_results: int) -> list[dict]:
    """Twitter API v2 の Recent Search エンドポイントを呼ぶ。"""
    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {
        "query": f"{keyword} lang:ja -is:retweet",
        "max_results": min(max_results, 100),
        "tweet.fields": "created_at,author_id,text",
        "expansions": "author_id",
        "user.fields": "username",
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    tweets = data.get("data", [])
    users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}

    return [
        {
            "id": t["id"],
            "text": t["text"],
            "created_at": t.get("created_at", ""),
            "author": users.get(t.get("author_id", ""), "unknown"),
        }
        for t in tweets
    ]


def _search_tweets_mock(keyword: str, max_results: int) -> list[dict]:
    """APIキー未設定時に返すモックデータ。"""
    results = []
    for tweet in MOCK_TWEETS[:max_results]:
        t = tweet.copy()
        # キーワードをテキストに自然に混ぜる
        if keyword and keyword not in t["text"]:
            t["text"] = t["text"].replace("#AI", f"#{keyword}")
        results.append(t)
    return results


def is_using_mock() -> bool:
    return not bool(BEARER_TOKEN)
