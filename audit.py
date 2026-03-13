#!/usr/bin/env python3
"""
AIコンテンツ監査ツール
Anthropic APIを使用してウェブページのSEO・コンテンツ品質を分析し、
Bootstrap HTMLレポートを生成します。

使い方: python audit.py urls.txt
"""

import sys
import os
import time
import json
import re
import argparse
from collections import Counter
from urllib.parse import urlparse
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import anthropic

# ─── 定数 ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"
RATE_LIMIT_DELAY = 1          # API呼び出し間の待機秒数
REQUEST_TIMEOUT = 30          # HTTPリクエストタイムアウト
MAX_CONTENT_LENGTH = 8000     # APIに送るコンテンツの最大文字数


# ─── ページ取得 ───────────────────────────────────────────────────────────────
def fetch_page(url: str) -> dict:
    """URLからページを取得して構造化データを返す。"""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ContentAuditBot/1.0)",
        "Accept-Language": "ja,en;q=0.9",
    }
    resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc_text = (
        meta_desc_tag.get("content", "")
        if meta_desc_tag
        else ""
    )

    h1_tags = [h.get_text(strip=True) for h in soup.find_all("h1")]
    h2_tags = [h.get_text(strip=True) for h in soup.find_all("h2")]
    h3_tags = [h.get_text(strip=True) for h in soup.find_all("h3")]

    # ナビ・フッター等の不要タグを除去してからテキスト抽出
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    paragraphs = [
        p.get_text(strip=True)
        for p in soup.find_all("p")
        if p.get_text(strip=True)
    ]
    body_text = soup.get_text(separator="\n", strip=True)

    return {
        "url": url,
        "title": title_text,
        "meta_description": meta_desc_text,
        "h1_tags": h1_tags,
        "h2_tags": h2_tags,
        "h3_tags": h3_tags,
        "paragraphs": paragraphs,
        "body_text": body_text,
    }


# ─── SEOスコア計算 ───────────────────────────────────────────────────────────
def calculate_seo_score(page: dict) -> dict:
    """タイトル・メタ・見出し構造からSEOスコア（0〜100）を算出する。"""
    score = 0
    issues = []

    # タイトル（20点）
    if page["title"]:
        score += 10
        tlen = len(page["title"])
        if 30 <= tlen <= 70:
            score += 10
        else:
            issues.append(
                f"タイトル文字数が最適ではありません（{tlen}文字、推奨: 30〜70文字）"
            )
    else:
        issues.append("タイトルタグがありません")

    # メタディスクリプション（20点）
    if page["meta_description"]:
        score += 10
        dlen = len(page["meta_description"])
        if 70 <= dlen <= 160:
            score += 10
        else:
            issues.append(
                f"メタディスクリプションの文字数が最適ではありません（{dlen}文字、推奨: 70〜160文字）"
            )
    else:
        issues.append("メタディスクリプションがありません")

    # H1タグ（20点）
    h1_count = len(page["h1_tags"])
    if h1_count == 1:
        score += 20
    elif h1_count > 1:
        score += 10
        issues.append(f"H1タグが複数存在します（{h1_count}個、推奨: 1個）")
    else:
        issues.append("H1タグがありません")

    # H2/H3タグ（20点）
    if page["h2_tags"]:
        score += 10
    else:
        issues.append("H2タグがありません")
    if page["h3_tags"]:
        score += 10

    # コンテンツ量（20点）
    wc = len(page["body_text"])
    if wc >= 500:
        score += 20
    elif wc >= 200:
        score += 10
        issues.append(f"コンテンツが少ない可能性があります（{wc}文字）")
    else:
        issues.append(f"コンテンツが非常に少ないです（{wc}文字）")

    return {
        "score": score,
        "issues": issues,
        "title": page["title"],
        "title_length": len(page["title"]),
        "meta_description": page["meta_description"],
        "meta_description_length": len(page["meta_description"]),
        "h1_count": h1_count,
        "h2_count": len(page["h2_tags"]),
        "h3_count": len(page["h3_tags"]),
        "h1_tags": page["h1_tags"],
        "h2_tags": page["h2_tags"][:5],
        "h3_tags": page["h3_tags"][:5],
    }


# ─── キーワード密度 ──────────────────────────────────────────────────────────
STOP_WORDS = {
    # 英語
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "this", "that", "these", "those", "it",
    "its", "we", "our", "you", "your", "they", "their", "he", "she",
    "his", "her", "not", "no", "so", "as", "if", "when", "where", "how",
    # 日本語助詞・助動詞など
    "の", "に", "は", "を", "が", "と", "で", "て", "から", "より",
    "も", "か", "な", "や", "へ", "など", "でも", "まで", "ので",
    "する", "した", "して", "いる", "ある", "なる", "れる", "られる",
    "です", "ます", "ない", "ません", "ました", "します", "れた", "こと",
    "もの", "ため", "それ", "これ", "あの", "その", "どの", "という",
}


def calculate_keyword_density(text: str) -> list:
    """テキストからキーワード密度トップ10を算出する。"""
    words = re.findall(r"[a-zA-Z]{3,}|[\u3040-\u9fff]{2,}", text.lower())
    filtered = [w for w in words if w not in STOP_WORDS and len(w) > 1]

    if not filtered:
        return []

    total = len(filtered)
    top10 = Counter(filtered).most_common(10)
    return [
        {"word": w, "count": c, "density": round(c / total * 100, 2)}
        for w, c in top10
    ]


# ─── 読みやすさ ──────────────────────────────────────────────────────────────
def calculate_readability(page: dict) -> dict:
    """1文の平均文字数・段落の平均文字数などを算出する。"""
    body_text = page["body_text"]
    paragraphs = page["paragraphs"]

    if not body_text:
        return {
            "avg_chars_per_sentence": 0,
            "avg_paragraph_length": 0,
            "total_paragraphs": 0,
            "total_sentences": 0,
            "total_chars": 0,
            "readability_score": 0,
        }

    sentences = [
        s.strip()
        for s in re.split(r"[。！？!?.]+", body_text)
        if len(s.strip()) > 5
    ]

    avg_chars = (
        sum(len(s) for s in sentences) / len(sentences) if sentences else 0
    )
    avg_para = (
        sum(len(p) for p in paragraphs) / len(paragraphs) if paragraphs else 0
    )

    # 日本語は1文40〜80文字が読みやすい目安
    if avg_chars <= 80:
        score = 90
    elif avg_chars <= 120:
        score = 70
    elif avg_chars <= 160:
        score = 50
    else:
        score = 30

    return {
        "avg_chars_per_sentence": round(avg_chars, 1),
        "avg_paragraph_length": round(avg_para, 1),
        "total_paragraphs": len(paragraphs),
        "total_sentences": len(sentences),
        "total_chars": len(body_text),
        "readability_score": score,
    }


# ─── AI分析（Anthropic API） ─────────────────────────────────────────────────
def analyze_with_ai(client: anthropic.Anthropic, page: dict) -> dict:
    """Claude claude-opus-4-6 でページを分析し、構造化データを返す。"""
    content_preview = page["body_text"][:MAX_CONTENT_LENGTH]

    prompt = f"""以下のウェブページを分析してください。

URL: {page['url']}
タイトル: {page['title']}
メタディスクリプション: {page['meta_description']}
H1タグ: {', '.join(page['h1_tags'][:3])}
H2タグ: {', '.join(page['h2_tags'][:5])}

ページ本文（先頭{MAX_CONTENT_LENGTH}文字）:
{content_preview}

---
以下の形式のJSONのみを返してください（マークダウンのコードブロック不要）:

{{
    "overall_score": <整数 0-100 総合スコア>,
    "content_quality": <整数 0-100 コンテンツ品質スコア>,
    "seo_assessment": "<SEO総合評価 2〜3文>",
    "readability_assessment": "<読みやすさ評価 2〜3文>",
    "improvements": [
        "<改善提案1>",
        "<改善提案2>",
        "<改善提案3>",
        "<改善提案4>",
        "<改善提案5>"
    ],
    "strengths": [
        "<強み1>",
        "<強み2>"
    ]
}}"""

    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2048,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    text_content = ""
    for block in response.content:
        if block.type == "text":
            text_content = block.text
            break

    # JSON部分を抽出してパース
    json_match = re.search(r"\{[\s\S]*\}", text_content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {
        "overall_score": 50,
        "content_quality": 50,
        "seo_assessment": "AI分析結果の解析に失敗しました。",
        "readability_assessment": "AI分析結果の解析に失敗しました。",
        "improvements": ["レスポンスのJSON解析に失敗しました。再実行してください。"],
        "strengths": [],
    }


# ─── HTMLレポート生成 ─────────────────────────────────────────────────────────
def _badge_cls(score: int) -> str:
    if score >= 80:
        return "bg-success"
    if score >= 60:
        return "bg-warning text-dark"
    if score >= 40:
        return "bg-orange"
    return "bg-danger"


def _bar_cls(score: int) -> str:
    if score >= 80:
        return "bg-success"
    if score >= 60:
        return "bg-warning"
    if score >= 40:
        return "bg-info"
    return "bg-danger"


def _txt_cls(score: int) -> str:
    if score >= 80:
        return "success"
    if score >= 60:
        return "warning"
    return "danger"


def _score_card(label: str, score: int) -> str:
    return f"""
        <div class="col-6 col-md-3">
          <div class="card bg-light h-100 text-center">
            <div class="card-body py-3">
              <h6 class="text-muted small mb-1">{label}</h6>
              <div class="display-6 fw-bold text-{_txt_cls(score)}">{score}</div>
              <div class="progress mt-2" style="height:5px">
                <div class="progress-bar {_bar_cls(score)}" style="width:{score}%"></div>
              </div>
            </div>
          </div>
        </div>"""


def _keyword_rows(keywords: list) -> str:
    if not keywords:
        return '<tr><td colspan="3" class="text-center text-muted">キーワードデータなし</td></tr>'
    rows = []
    for kw in keywords:
        bar_w = min(kw["density"] * 10, 100)
        rows.append(
            f"""<tr>
              <td><strong>{kw['word']}</strong></td>
              <td class="text-center">{kw['count']}</td>
              <td>
                <div class="d-flex align-items-center gap-2">
                  <div class="progress flex-grow-1" style="height:7px">
                    <div class="progress-bar bg-info" style="width:{bar_w}%"></div>
                  </div>
                  <small class="text-nowrap">{kw['density']}%</small>
                </div>
              </td>
            </tr>"""
        )
    return "\n".join(rows)


def _tag_list(tags: list, limit: int = 5) -> str:
    if not tags:
        return '<span class="text-muted small">なし</span>'
    items = []
    for t in tags[:limit]:
        short = t[:70] + ("…" if len(t) > 70 else "")
        items.append(f'<code class="d-block mb-1 text-wrap">{short}</code>')
    return "\n".join(items)


def _list_items(items: list, icon: str = "bi-arrow-right-circle text-primary") -> str:
    if not items:
        return '<li class="list-group-item border-0 ps-0 text-muted">データなし</li>'
    return "\n".join(
        f'<li class="list-group-item border-0 ps-0">'
        f'<i class="bi {icon} me-2"></i>{item}</li>'
        for item in items
    )


def _page_card(idx: int, result: dict) -> str:
    url = result["url"]
    domain = urlparse(url).netloc

    if result.get("error"):
        return f"""
    <div class="card mb-4 border-danger" id="page-{idx}">
      <div class="card-header bg-danger text-white">
        <h5 class="mb-0">
          <span class="badge bg-secondary me-2">#{idx}</span>
          <span class="badge bg-light text-danger me-2">エラー</span>{domain}
        </h5>
        <small class="opacity-75">{url}</small>
      </div>
      <div class="card-body">
        <div class="alert alert-danger mb-0">
          <i class="bi bi-exclamation-triangle-fill me-2"></i>
          <strong>エラー:</strong> {result['error']}
        </div>
      </div>
    </div>"""

    seo = result["seo"]
    rd = result["readability"]
    kw = result["keywords"]
    ai = result["ai_analysis"]

    overall = ai["overall_score"]
    seo_sc = seo["score"]
    read_sc = rd["readability_score"]
    quality = ai.get("content_quality", 50)

    # SEO課題リスト
    if seo["issues"]:
        seo_issues_html = "\n".join(
            f'<li class="text-warning mb-1">'
            f'<i class="bi bi-exclamation-circle me-1"></i>{iss}</li>'
            for iss in seo["issues"]
        )
    else:
        seo_issues_html = (
            '<li class="text-success">'
            '<i class="bi bi-check-circle me-1"></i>主なSEO問題なし</li>'
        )

    # 読みやすさアラートクラス
    rd_alert = "success" if read_sc >= 80 else ("warning" if read_sc >= 60 else "danger")
    rd_label = "（読みやすい）" if read_sc >= 80 else ("（改善推奨）" if read_sc >= 60 else "（要改善）")

    # H1文字数バッジクラス
    h1_badge = "bg-success" if seo["h1_count"] == 1 else ("bg-warning text-dark" if seo["h1_count"] > 1 else "bg-danger")
    h2_badge = "bg-success" if seo["h2_count"] > 0 else "bg-danger"

    # 文字数バッジクラス
    avg_badge = "bg-success" if rd["avg_chars_per_sentence"] <= 80 else ("bg-warning text-dark" if rd["avg_chars_per_sentence"] <= 120 else "bg-danger")

    return f"""
    <div class="card mb-4 shadow-sm" id="page-{idx}">
      <div class="card-header">
        <div class="d-flex justify-content-between align-items-start flex-wrap gap-2">
          <div>
            <h5 class="mb-1">
              <span class="badge bg-secondary me-2">#{idx}</span>{domain}
            </h5>
            <small class="text-muted">
              <a href="{url}" target="_blank" class="text-decoration-none">{url}</a>
            </small>
          </div>
          <span class="badge {_badge_cls(overall)} fs-6 px-3 py-2">総合スコア: {overall}/100</span>
        </div>
      </div>

      <div class="card-body">
        <!-- スコアカード -->
        <div class="row g-3 mb-4">
          {_score_card("総合スコア", overall)}
          {_score_card("SEOスコア", seo_sc)}
          {_score_card("読みやすさ", read_sc)}
          {_score_card("コンテンツ品質", quality)}
        </div>

        <!-- タブ -->
        <ul class="nav nav-tabs" role="tablist">
          <li class="nav-item">
            <button class="nav-link active" data-bs-toggle="tab" data-bs-target="#seo-{idx}">
              <i class="bi bi-search me-1"></i>SEO分析
            </button>
          </li>
          <li class="nav-item">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#kw-{idx}">
              <i class="bi bi-bar-chart me-1"></i>キーワード
            </button>
          </li>
          <li class="nav-item">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#rd-{idx}">
              <i class="bi bi-book me-1"></i>読みやすさ
            </button>
          </li>
          <li class="nav-item">
            <button class="nav-link" data-bs-toggle="tab" data-bs-target="#imp-{idx}">
              <i class="bi bi-lightbulb me-1"></i>AI改善提案
            </button>
          </li>
        </ul>

        <div class="tab-content border border-top-0 rounded-bottom p-3">

          <!-- SEO分析タブ -->
          <div class="tab-pane fade show active" id="seo-{idx}">
            <div class="row g-3 mt-1">
              <div class="col-md-6">
                <table class="table table-sm">
                  <tbody>
                    <tr>
                      <td><strong>タイトル</strong></td>
                      <td>
                        <span class="badge {'bg-success' if seo['title'] else 'bg-danger'}">
                          {'あり' if seo['title'] else 'なし'}
                        </span>
                        <small class="ms-2 text-muted">{seo['title_length']}文字</small>
                      </td>
                    </tr>
                    <tr>
                      <td><strong>メタディスクリプション</strong></td>
                      <td>
                        <span class="badge {'bg-success' if seo['meta_description'] else 'bg-danger'}">
                          {'あり' if seo['meta_description'] else 'なし'}
                        </span>
                        <small class="ms-2 text-muted">{seo['meta_description_length']}文字</small>
                      </td>
                    </tr>
                    <tr>
                      <td><strong>H1タグ数</strong></td>
                      <td><span class="badge {h1_badge}">{seo['h1_count']}個</span></td>
                    </tr>
                    <tr>
                      <td><strong>H2タグ数</strong></td>
                      <td><span class="badge {h2_badge}">{seo['h2_count']}個</span></td>
                    </tr>
                    <tr>
                      <td><strong>H3タグ数</strong></td>
                      <td><span class="badge bg-info">{seo['h3_count']}個</span></td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="col-md-6">
                <h6 class="text-muted">SEO課題</h6>
                <ul class="list-unstyled">{seo_issues_html}</ul>
                <h6 class="text-muted mt-3">AI評価</h6>
                <p class="text-muted small">{ai.get('seo_assessment', '')}</p>
              </div>
            </div>
            <div class="row g-3 mt-1">
              <div class="col-md-4">
                <h6 class="text-muted">H1タグ</h6>
                {_tag_list(seo['h1_tags'])}
              </div>
              <div class="col-md-4">
                <h6 class="text-muted">H2タグ（上位5件）</h6>
                {_tag_list(seo['h2_tags'])}
              </div>
              <div class="col-md-4">
                <h6 class="text-muted">H3タグ（上位5件）</h6>
                {_tag_list(seo['h3_tags'])}
              </div>
            </div>
          </div>

          <!-- キーワードタブ -->
          <div class="tab-pane fade" id="kw-{idx}">
            <h6 class="text-muted mt-2 mb-3">キーワード密度トップ10</h6>
            <div class="table-responsive">
              <table class="table table-sm table-hover">
                <thead class="table-light">
                  <tr>
                    <th>キーワード</th>
                    <th class="text-center">出現回数</th>
                    <th>密度</th>
                  </tr>
                </thead>
                <tbody>{_keyword_rows(kw)}</tbody>
              </table>
            </div>
          </div>

          <!-- 読みやすさタブ -->
          <div class="tab-pane fade" id="rd-{idx}">
            <div class="row g-3 mt-1">
              <div class="col-md-6">
                <table class="table table-sm">
                  <tbody>
                    <tr>
                      <td><strong>1文の平均文字数</strong></td>
                      <td><span class="badge {avg_badge}">{rd['avg_chars_per_sentence']}文字</span></td>
                    </tr>
                    <tr>
                      <td><strong>段落の平均文字数</strong></td>
                      <td><span class="badge bg-info">{rd['avg_paragraph_length']}文字</span></td>
                    </tr>
                    <tr>
                      <td><strong>総段落数</strong></td>
                      <td>{rd['total_paragraphs']}段落</td>
                    </tr>
                    <tr>
                      <td><strong>総文数</strong></td>
                      <td>{rd['total_sentences']}文</td>
                    </tr>
                    <tr>
                      <td><strong>総文字数</strong></td>
                      <td>{rd['total_chars']:,}文字</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="col-md-6">
                <h6 class="text-muted">読みやすさ評価</h6>
                <p class="text-muted small">{ai.get('readability_assessment', '')}</p>
                <div class="alert alert-{rd_alert} py-2">
                  <strong>読みやすさスコア: {read_sc}/100</strong> {rd_label}
                </div>
              </div>
            </div>
          </div>

          <!-- AI改善提案タブ -->
          <div class="tab-pane fade" id="imp-{idx}">
            <div class="row g-3 mt-1">
              <div class="col-md-6">
                <h6 class="mb-3">
                  <i class="bi bi-lightbulb text-warning me-2"></i>改善提案
                </h6>
                <ul class="list-group list-group-flush">
                  {_list_items(ai.get('improvements', []), 'bi-arrow-right-circle text-primary')}
                </ul>
              </div>
              <div class="col-md-6">
                <h6 class="mb-3">
                  <i class="bi bi-star text-success me-2"></i>強み
                </h6>
                <ul class="list-group list-group-flush">
                  {_list_items(ai.get('strengths', []), 'bi-check-circle text-success')}
                </ul>
              </div>
            </div>
          </div>

        </div><!-- /tab-content -->
      </div><!-- /card-body -->
    </div>"""


def generate_html_report(results: list, output_path: str) -> None:
    """Bootstrap HTMLレポートをファイルに書き出す。"""
    timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    successful = [r for r in results if not r.get("error")]
    failed = [r for r in results if r.get("error")]

    avg_overall = (
        sum(r["ai_analysis"]["overall_score"] for r in successful) / len(successful)
        if successful else 0
    )
    avg_seo = (
        sum(r["seo"]["score"] for r in successful) / len(successful)
        if successful else 0
    )
    avg_rd = (
        sum(r["readability"]["readability_score"] for r in successful) / len(successful)
        if successful else 0
    )

    # サマリーテーブル行
    summary_rows = []
    for idx, r in enumerate(results, 1):
        domain = urlparse(r["url"]).netloc
        link = f'<a href="#page-{idx}">{domain}</a>'
        if r.get("error"):
            summary_rows.append(
                f"<tr><td>{idx}</td><td>{link}</td>"
                f'<td colspan="4"><span class="badge bg-danger">エラー</span></td></tr>'
            )
        else:
            ov = r["ai_analysis"]["overall_score"]
            ss = r["seo"]["score"]
            rs = r["readability"]["readability_score"]
            cq = r["ai_analysis"].get("content_quality", 50)
            summary_rows.append(
                f"<tr><td>{idx}</td><td>{link}</td>"
                f'<td><span class="badge {_badge_cls(ov)}">{ov}</span></td>'
                f'<td><span class="badge {_badge_cls(ss)}">{ss}</span></td>'
                f'<td><span class="badge {_badge_cls(rs)}">{rs}</span></td>'
                f'<td><span class="badge {_badge_cls(cq)}">{cq}</span></td></tr>'
            )

    summary_table = "\n".join(summary_rows)
    page_cards = "\n".join(_page_card(i, r) for i, r in enumerate(results, 1))

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AIコンテンツ監査レポート</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.0/font/bootstrap-icons.css" rel="stylesheet">
  <style>
    body {{ background-color: #f8f9fa; }}
    .hero {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }}
    code {{ font-size: .85em; word-break: break-all; }}
    .nav-tabs .nav-link {{ color: #495057; }}
    .nav-tabs .nav-link.active {{ font-weight: 600; }}
  </style>
</head>
<body>

<div class="hero text-white py-5 mb-4">
  <div class="container">
    <div class="row align-items-center">
      <div class="col-md-8">
        <h1 class="display-5 fw-bold mb-1">
          <i class="bi bi-robot me-3"></i>AIコンテンツ監査レポート
        </h1>
        <p class="lead mb-0 opacity-75">Powered by Claude claude-opus-4-6 (Anthropic)</p>
      </div>
      <div class="col-md-4 text-md-end opacity-75">
        <div><i class="bi bi-calendar3 me-1"></i>{timestamp}</div>
        <div><i class="bi bi-globe me-1"></i>{len(results)}ページ分析完了</div>
        <div>
          <span class="badge bg-light text-success me-1">成功: {len(successful)}</span>
          <span class="badge bg-light text-danger">エラー: {len(failed)}</span>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="container pb-5">

  <!-- サマリー統計 -->
  <div class="row g-4 mb-5">
    <div class="col-6 col-md-3">
      <div class="card text-center h-100 shadow-sm">
        <div class="card-body py-4">
          <i class="bi bi-files fs-1 text-primary mb-2"></i>
          <h2 class="fw-bold">{len(results)}</h2>
          <p class="text-muted mb-0">分析ページ数</p>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card text-center h-100 shadow-sm">
        <div class="card-body py-4">
          <i class="bi bi-graph-up fs-1 text-{_txt_cls(int(avg_overall))} mb-2"></i>
          <h2 class="fw-bold">{avg_overall:.1f}</h2>
          <p class="text-muted mb-0">平均総合スコア</p>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card text-center h-100 shadow-sm">
        <div class="card-body py-4">
          <i class="bi bi-search fs-1 text-{_txt_cls(int(avg_seo))} mb-2"></i>
          <h2 class="fw-bold">{avg_seo:.1f}</h2>
          <p class="text-muted mb-0">平均SEOスコア</p>
        </div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card text-center h-100 shadow-sm">
        <div class="card-body py-4">
          <i class="bi bi-book fs-1 text-{_txt_cls(int(avg_rd))} mb-2"></i>
          <h2 class="fw-bold">{avg_rd:.1f}</h2>
          <p class="text-muted mb-0">平均読みやすさ</p>
        </div>
      </div>
    </div>
  </div>

  <!-- サマリーテーブル -->
  <div class="card mb-5 shadow-sm">
    <div class="card-header bg-dark text-white">
      <h5 class="mb-0"><i class="bi bi-table me-2"></i>サマリーテーブル</h5>
    </div>
    <div class="card-body p-0">
      <div class="table-responsive">
        <table class="table table-hover mb-0">
          <thead class="table-dark">
            <tr>
              <th>#</th><th>ドメイン</th>
              <th>総合</th><th>SEO</th><th>読みやすさ</th><th>品質</th>
            </tr>
          </thead>
          <tbody>{summary_table}</tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- 個別ページレポート -->
  <h3 class="mb-4"><i class="bi bi-file-text me-2"></i>個別ページレポート</h3>
  {page_cards}

  <div class="text-center text-muted mt-5 pt-4 border-top">
    <p class="mb-1">
      <i class="bi bi-robot me-1"></i>
      AIコンテンツ監査ツール — Claude claude-opus-4-6 (Anthropic) によるコンテンツ分析
    </p>
    <p class="small">生成日時: {timestamp}</p>
  </div>

</div><!-- /container -->

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


# ─── URL単体の監査 ────────────────────────────────────────────────────────────
def audit_url(client: anthropic.Anthropic, url: str, idx: int, total: int) -> dict:
    """1つのURLを監査して結果dict を返す。エラー時は error キーを含む。"""
    print(f"[{idx}/{total}] 分析中: {url}")
    try:
        print("  → ページ取得中…")
        page = fetch_page(url)

        print("  → メトリクス計算中…")
        seo = calculate_seo_score(page)
        keywords = calculate_keyword_density(page["body_text"])
        readability = calculate_readability(page)

        print("  → AI分析中（Anthropic API）…")
        ai_analysis = analyze_with_ai(client, page)

        print(f"  ✓ 完了（総合スコア: {ai_analysis.get('overall_score', 'N/A')}）")
        return {
            "url": url,
            "seo": seo,
            "keywords": keywords,
            "readability": readability,
            "ai_analysis": ai_analysis,
        }

    except requests.exceptions.ConnectionError as e:
        msg = f"接続エラー: {e}"
    except requests.exceptions.Timeout:
        msg = f"タイムアウト（{REQUEST_TIMEOUT}秒）"
    except requests.exceptions.HTTPError as e:
        msg = f"HTTPエラー: {e}"
    except requests.exceptions.RequestException as e:
        msg = f"リクエストエラー: {e}"
    except Exception as e:
        msg = f"予期しないエラー: {e}"

    print(f"  ✗ スキップ: {msg}")
    return {"url": url, "error": msg}


# ─── エントリーポイント ────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="AIコンテンツ監査ツール — Anthropic APIでウェブページを分析します"
    )
    parser.add_argument("urls_file", help="分析するURLリストのテキストファイル")
    parser.add_argument(
        "--output", "-o",
        default=os.path.join(OUTPUT_DIR, "report.html"),
        help="出力HTMLファイルのパス（デフォルト: output/report.html）",
    )
    args = parser.parse_args()

    # URLファイルの読み込み
    try:
        with open(args.urls_file, encoding="utf-8") as f:
            urls = [
                line.strip()
                for line in f
                if line.strip() and not line.startswith("#")
            ]
    except FileNotFoundError:
        print(f"エラー: URLファイル '{args.urls_file}' が見つかりません")
        sys.exit(1)

    if not urls:
        print("エラー: URLが見つかりません（#で始まる行はコメントとして無視されます）")
        sys.exit(1)

    # Anthropicクライアントの初期化
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("エラー: ANTHROPIC_API_KEY 環境変数が設定されていません")
        sys.exit(1)
    client = anthropic.Anthropic(api_key=api_key)

    # 出力ディレクトリの準備
    out_dir = os.path.dirname(args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("AIコンテンツ監査ツール 開始")
    print(f"分析URL数 : {len(urls)}")
    print(f"出力先    : {args.output}")
    print("=" * 60)

    results = []
    for idx, url in enumerate(urls, 1):
        result = audit_url(client, url, idx, len(urls))
        results.append(result)

        if idx < len(urls):
            print(f"  待機中… ({RATE_LIMIT_DELAY}秒)")
            time.sleep(RATE_LIMIT_DELAY)
        print("-" * 60)

    print("レポート生成中…")
    generate_html_report(results, args.output)

    successful = sum(1 for r in results if not r.get("error"))
    failed = len(results) - successful

    print(f"\n✓ レポート生成完了: {args.output}")
    print(f"  成功: {successful}ページ")
    if failed:
        print(f"  エラー: {failed}ページ")


if __name__ == "__main__":
    main()
