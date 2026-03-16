"""
レポート自動生成モジュール
Claudeが分析結果を日本語で要約し、HTMLレポートを生成する。
"""

import json
import re
import anthropic
from datetime import datetime


def _generate_summary_text(client: anthropic.Anthropic, keyword: str, summary: dict,
                            trend: dict, risk: dict, influencers: list) -> str:
    """Claudeに分析レポートの文章生成を依頼する"""
    top_influencers = [f"@{i['author']}（スコア{i['influence_score']}）" for i in influencers[:3]]

    prompt = f"""以下のSNS分析データを基に、ブランド担当者向けの週次レポートを日本語で作成してください。

## 分析キーワード: {keyword}
## 分析日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}

### センチメントサマリー
- 総投稿数: {summary['total']}件
- ポジティブ: {summary['positive_pct']}%
- ネガティブ: {summary['negative_pct']}%
- 平均感情スコア: {summary['avg_score']}/100

### 感情分析（平均値）
- 喜び: {summary['emotions_avg'].get('joy', 0)}, 怒り: {summary['emotions_avg'].get('anger', 0)}
- 不安: {summary['emotions_avg'].get('anxiety', 0)}, 信頼: {summary['emotions_avg'].get('trust', 0)}
- 期待: {summary['emotions_avg'].get('anticipation', 0)}

### トレンド予測
- モメンタム: {trend.get('momentum', '不明')}
- 予測: {trend.get('prediction', '不明')}
- 注目キーワード: {', '.join(trend.get('trending_keywords', []))}

### 炎上リスク
- スコア: {risk['score']}/100 ({risk['level']})
- 理由: {risk['reason']}

### 主要インフルエンサー
{', '.join(top_influencers) if top_influencers else 'なし'}

以下の構成で200〜300字のレポートを作成してください:
1. 全体評価（1文）
2. 注目ポイント（2〜3文）
3. 推奨アクション（1〜2文）"""

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def generate_report(client: anthropic.Anthropic, keyword: str, summary: dict,
                    trend: dict, risk: dict, influencers: list, tweets: list) -> str:
    """
    HTML形式のレポートを生成して文字列で返す。
    """
    summary_text = _generate_summary_text(client, keyword, summary, trend, risk, influencers)
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    risk_color = {"low": "#16a34a", "warning": "#d97706", "critical": "#dc2626"}.get(risk["level"], "#4b5563")
    risk_label = {"low": "低リスク", "warning": "要注意", "critical": "緊急アラート"}.get(risk["level"], "不明")
    momentum_icon = {"rising": "↑", "stable": "→", "falling": "↓"}.get(trend.get("momentum", "stable"), "→")

    influencer_rows = ""
    for inf in influencers:
        label_map = {"positive": "ポジティブ", "negative": "ネガティブ", "neutral": "ニュートラル"}
        color_map = {"positive": "#16a34a", "negative": "#dc2626", "neutral": "#6b7280"}
        sentiment_color = color_map.get(inf["sentiment_label"], "#6b7280")
        influencer_rows += f"""
        <tr>
          <td style="padding:8px 12px;">@{inf['author']}</td>
          <td style="padding:8px 12px;text-align:right;">{inf['follower_count']:,}</td>
          <td style="padding:8px 12px;text-align:right;">{inf['influence_score']}</td>
          <td style="padding:8px 12px;color:{sentiment_color};">{label_map.get(inf['sentiment_label'], '')}</td>
        </tr>"""

    trending_kw_html = " ".join(
        f'<span style="background:#1e3a5f;color:#93c5fd;padding:3px 10px;border-radius:9999px;font-size:13px;">{kw}</span>'
        for kw in trend.get("trending_keywords", [])
    )

    emotions_avg = summary.get("emotions_avg", {})
    emotion_bars = ""
    emotion_labels = {
        "joy": "喜び", "anger": "怒り", "sadness": "悲しみ", "surprise": "驚き",
        "anxiety": "不安", "disgust": "嫌悪", "trust": "信頼", "anticipation": "期待",
    }
    emotion_colors = {
        "joy": "#16a34a", "anger": "#dc2626", "sadness": "#3b82f6", "surprise": "#8b5cf6",
        "anxiety": "#f59e0b", "disgust": "#6b7280", "trust": "#0ea5e9", "anticipation": "#ec4899",
    }
    for key, label in emotion_labels.items():
        val = emotions_avg.get(key, 0)
        color = emotion_colors[key]
        emotion_bars += f"""
        <div style="margin-bottom:8px;">
          <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
            <span>{label}</span><span>{val}</span>
          </div>
          <div style="background:#1f2937;border-radius:4px;height:8px;">
            <div style="background:{color};width:{val}%;height:8px;border-radius:4px;"></div>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SNS分析レポート — {keyword}</title>
  <style>
    body {{ font-family: 'Helvetica Neue', sans-serif; background:#0f172a; color:#e2e8f0; margin:0; padding:32px; }}
    .container {{ max-width:860px; margin:0 auto; }}
    h1 {{ font-size:24px; color:#f1f5f9; margin-bottom:4px; }}
    .meta {{ color:#64748b; font-size:13px; margin-bottom:32px; }}
    .card {{ background:#1e293b; border-radius:12px; padding:24px; margin-bottom:20px; border:1px solid #334155; }}
    .card h2 {{ font-size:15px; color:#94a3b8; margin:0 0 16px 0; text-transform:uppercase; letter-spacing:.5px; }}
    .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
    .stat {{ background:#0f172a; border-radius:8px; padding:16px; text-align:center; }}
    .stat .val {{ font-size:32px; font-weight:700; }}
    .stat .lbl {{ font-size:12px; color:#64748b; margin-top:4px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th {{ text-align:left; padding:8px 12px; color:#64748b; font-weight:500; border-bottom:1px solid #334155; }}
    tr:nth-child(even) {{ background:#0f172a; }}
    .badge {{ display:inline-block; padding:3px 10px; border-radius:9999px; font-size:12px; font-weight:600; }}
    @media print {{ body {{ background:white; color:black; }} .card {{ border:1px solid #ccc; background:white; }} }}
  </style>
</head>
<body>
<div class="container">
  <h1>SNS分析レポート — #{keyword}</h1>
  <p class="meta">生成日時: {now} &nbsp;|&nbsp; 分析件数: {summary['total']}件</p>

  <!-- サマリー -->
  <div class="card">
    <h2>センチメントサマリー</h2>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
      <div class="stat"><div class="val" style="color:#f1f5f9;">{summary['total']}</div><div class="lbl">総投稿数</div></div>
      <div class="stat"><div class="val" style="color:#16a34a;">{summary['positive_pct']}%</div><div class="lbl">ポジティブ</div></div>
      <div class="stat"><div class="val" style="color:#dc2626;">{summary['negative_pct']}%</div><div class="lbl">ネガティブ</div></div>
      <div class="stat"><div class="val" style="color:#60a5fa;">{summary['avg_score']}</div><div class="lbl">平均スコア</div></div>
    </div>
  </div>

  <!-- AI要約 -->
  <div class="card">
    <h2>AI生成サマリー</h2>
    <p style="line-height:1.8;white-space:pre-wrap;">{summary_text}</p>
  </div>

  <!-- 炎上リスク -->
  <div class="card">
    <h2>炎上リスク</h2>
    <div style="display:flex;align-items:center;gap:24px;">
      <div style="font-size:56px;font-weight:700;color:{risk_color};">{risk['score']}</div>
      <div>
        <span class="badge" style="background:{risk_color}20;color:{risk_color};margin-bottom:8px;">{risk_label}</span>
        <p style="margin:0;font-size:14px;color:#94a3b8;">{risk['reason']}</p>
        <p style="margin:4px 0 0;font-size:12px;color:#64748b;">ネガティブ率 {risk['neg_rate']}% &nbsp;|&nbsp; 増加速度 {risk['velocity']:+.3f}</p>
      </div>
    </div>
  </div>

  <div class="grid2">
    <!-- トレンド予測 -->
    <div class="card">
      <h2>トレンド予測</h2>
      <p style="font-size:28px;margin:0 0 8px;">{momentum_icon} <span style="font-size:15px;color:#94a3b8;">{trend.get('momentum','').upper()}</span></p>
      <p style="font-size:14px;margin:0 0 12px;line-height:1.7;">{trend.get('prediction','')}</p>
      <p style="font-size:12px;color:#64748b;margin:0 0 8px;">ピーク予測: {trend.get('peak_time','不明')}</p>
      <div style="margin-top:12px;">{trending_kw_html}</div>
    </div>

    <!-- 感情分析 -->
    <div class="card">
      <h2>8感情の平均強度</h2>
      {emotion_bars}
    </div>
  </div>

  <!-- インフルエンサー -->
  <div class="card">
    <h2>インフルエンサー TOP5</h2>
    <table>
      <thead><tr><th>アカウント</th><th style="text-align:right;">フォロワー</th><th style="text-align:right;">影響力スコア</th><th>センチメント</th></tr></thead>
      <tbody>{influencer_rows}</tbody>
    </table>
  </div>

  <p style="text-align:center;font-size:11px;color:#334155;margin-top:32px;">Generated by SNS分析ツール powered by Claude</p>
</div>
</body>
</html>"""

    return html
