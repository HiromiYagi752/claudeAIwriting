"""
Twitter API v2 クライアント（モックデータ切り替え対応）

環境変数 TWITTER_BEARER_TOKEN が設定されている場合は実APIを使用。
未設定の場合はモックデータを返す。
"""

import os
import requests

BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN")


MOCK_TWEETS = [
    {
        "id": "1", "text": "AIの進化が本当にすごい！毎日新しい発見があって楽しい。#AI",
        "created_at": "2026-03-16T08:00:00Z", "author": "tech_influencer_jp",
        "follower_count": 52000, "likes_count": 430, "retweet_count": 120,
    },
    {
        "id": "2", "text": "最近のAIツールは使いにくいものが多くて困る。もっとシンプルにしてほしい。#AI",
        "created_at": "2026-03-16T09:00:00Z", "author": "user_b",
        "follower_count": 980, "likes_count": 22, "retweet_count": 5,
    },
    {
        "id": "3", "text": "AIについて勉強中。まだよくわからないけど面白そう。#AI",
        "created_at": "2026-03-16T10:00:00Z", "author": "user_c",
        "follower_count": 310, "likes_count": 8, "retweet_count": 1,
    },
    {
        "id": "4", "text": "AIで業務効率が3倍になった！これは革命だと思う。#AI #生産性",
        "created_at": "2026-03-16T11:00:00Z", "author": "startup_ceo",
        "follower_count": 28000, "likes_count": 890, "retweet_count": 340,
    },
    {
        "id": "5", "text": "AIに仕事を奪われそうで不安。将来どうなるんだろう…#AI",
        "created_at": "2026-03-16T12:00:00Z", "author": "user_e",
        "follower_count": 1200, "likes_count": 67, "retweet_count": 18,
    },
    {
        "id": "6", "text": "ChatGPTとClaudeを比較してみたけど、どちらも素晴らしいね。#AI",
        "created_at": "2026-03-16T13:00:00Z", "author": "ai_reviewer",
        "follower_count": 15000, "likes_count": 210, "retweet_count": 55,
    },
    {
        "id": "7", "text": "AIのバイアス問題はまだ解決されていない。もっと議論が必要。#AI",
        "created_at": "2026-03-16T14:00:00Z", "author": "ethics_researcher",
        "follower_count": 9800, "likes_count": 145, "retweet_count": 72,
    },
    {
        "id": "8", "text": "AIアートが好きすぎる。毎日見てるだけで幸せ。#AI #アート",
        "created_at": "2026-03-16T15:00:00Z", "author": "user_h",
        "follower_count": 2400, "likes_count": 88, "retweet_count": 12,
    },
    {
        "id": "9", "text": "AIの規制が遅すぎる。このままでは危険だ。#AI",
        "created_at": "2026-03-16T16:00:00Z", "author": "policy_watcher",
        "follower_count": 6700, "likes_count": 310, "retweet_count": 130,
    },
    {
        "id": "10", "text": "AIで作った音楽、なかなか良かった！驚いた。#AI #音楽",
        "created_at": "2026-03-16T17:00:00Z", "author": "music_creator",
        "follower_count": 4300, "likes_count": 175, "retweet_count": 40,
    },
    {
        "id": "11", "text": "このAIサービス、個人情報の扱いが不透明で怖い。使うの辞めた。#AI",
        "created_at": "2026-03-16T17:30:00Z", "author": "security_blogger",
        "follower_count": 31000, "likes_count": 520, "retweet_count": 280,
    },
    {
        "id": "12", "text": "AIが書いた記事って見分けつかないよね。メディアの信頼性が心配。#AI",
        "created_at": "2026-03-16T18:00:00Z", "author": "journalist_jp",
        "follower_count": 22000, "likes_count": 410, "retweet_count": 195,
    },
    {
        "id": "13", "text": "AIの学習コスト削減技術、これは次のブレークスルーかも！期待大。#AI",
        "created_at": "2026-03-16T18:30:00Z", "author": "ml_engineer",
        "follower_count": 8500, "likes_count": 260, "retweet_count": 85,
    },
    {
        "id": "14", "text": "今日もAIに助けてもらいながら仕事終わった。ありがたい時代だな。#AI",
        "created_at": "2026-03-16T19:00:00Z", "author": "office_worker",
        "follower_count": 670, "likes_count": 31, "retweet_count": 3,
    },
    {
        "id": "15", "text": "AIがまた誤情報を生成した。こんなの信頼できない。#AI",
        "created_at": "2026-03-16T19:30:00Z", "author": "factcheck_jp",
        "follower_count": 18000, "likes_count": 490, "retweet_count": 220,
    },
    {
        "id": "16", "text": "AIの普及で格差が広がってる気がする。使える人と使えない人で差が出すぎ。#AI",
        "created_at": "2026-03-16T20:00:00Z", "author": "sociologist",
        "follower_count": 12000, "likes_count": 380, "retweet_count": 165,
    },
    {
        "id": "17", "text": "新しいAIモデル、推論がかなり改善された。ベンチマーク見て感動した。#AI",
        "created_at": "2026-03-16T20:30:00Z", "author": "ai_researcher",
        "follower_count": 45000, "likes_count": 1200, "retweet_count": 450,
    },
    {
        "id": "18", "text": "子供がAIに頼りすぎていて心配。自分で考える力が育たなくなる。#AI",
        "created_at": "2026-03-16T21:00:00Z", "author": "parent_concern",
        "follower_count": 3200, "likes_count": 155, "retweet_count": 48,
    },
    {
        "id": "19", "text": "AIが医療診断を補助してくれるようになって、地方の医療格差が少し縮まった。#AI",
        "created_at": "2026-03-16T21:30:00Z", "author": "rural_doctor",
        "follower_count": 7800, "likes_count": 620, "retweet_count": 290,
    },
    {
        "id": "20", "text": "AIツール乱立しすぎて何が良いかわからん。比較サイトほしい。#AI",
        "created_at": "2026-03-16T22:00:00Z", "author": "ordinary_user",
        "follower_count": 890, "likes_count": 44, "retweet_count": 9,
    },
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
        "tweet.fields": "created_at,author_id,text,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,public_metrics",
    }

    response = requests.get(url, headers=headers, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()

    tweets = data.get("data", [])
    users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

    return [
        {
            "id": t["id"],
            "text": t["text"],
            "created_at": t.get("created_at", ""),
            "author": users.get(t.get("author_id", ""), {}).get("username", "unknown"),
            "follower_count": users.get(t.get("author_id", ""), {}).get("public_metrics", {}).get("followers_count", 0),
            "likes_count": t.get("public_metrics", {}).get("like_count", 0),
            "retweet_count": t.get("public_metrics", {}).get("retweet_count", 0),
        }
        for t in tweets
    ]


def _search_tweets_mock(keyword: str, max_results: int) -> list[dict]:
    """APIキー未設定時に返すモックデータ。"""
    results = []
    for tweet in MOCK_TWEETS[:max_results]:
        t = tweet.copy()
        if keyword and keyword not in t["text"]:
            t["text"] = t["text"].replace("#AI", f"#{keyword}")
        results.append(t)
    return results


def is_using_mock() -> bool:
    return not bool(BEARER_TOKEN)
