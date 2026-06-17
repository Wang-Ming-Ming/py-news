---
name: market_content_extractor
description: Use this skill when the user provides Douyin, Xiaohongshu, web article, social-media, or finance-blogger links and wants market-related content extracted into structured data for stock-analysis skills. This skill cooperates with Agent-Reach for platform fetching and writes raw content plus cleaned market signals into data_social/.
---

# Market Content Extractor

This skill turns social-media and web content into structured market signals for other stock-analysis skills. It is not a trading recommender.

Use it when the user provides Douyin, Xiaohongshu, web article, finance blogger, video, or social links and asks to extract trends,观点,股票,板块,产业链, or market signals.

## Role Boundary

- Fetch content through Agent-Reach tools whenever available.
- Store raw fetched content and structured extraction results under `data_social/`.
- Separate facts, opinions, sentiment, hype, and risk warnings.
- Produce clean inputs for `morning_stock_picker`, `overnight_stock_picker`, and future short-term trend skills.
- Do not recommend buy/sell decisions inside this skill. Trading skills decide whether a signal is actionable.

## Agent-Reach Integration

Read Agent-Reach docs when platform details are needed:

- Agent-Reach router: `/Users/bawangchajiyouxiangongsi/.agents/skills/agent-reach/SKILL.md`
- Social reference: `/Users/bawangchajiyouxiangongsi/.agents/skills/agent-reach/references/social.md`

Preferred platform tools:

- Douyin: `mcporter call 'douyin.extract_douyin_text(share_link: "...")'` and `mcporter call 'douyin.parse_douyin_video_info(share_link: "...")'`
- Xiaohongshu: `xhs search`, `xhs read`, `xhs comments`; for profile links, first resolve/search recent notes because direct profile APIs may be unstable.
- Web/article fallback: Jina Reader or `curl` only when the content is ordinary web content, not as a replacement for unavailable social-platform tools.

If a platform tool is unavailable, record the source as `pending_tool_setup` instead of pretending the content was read.

Douyin audio/text extraction requires `DASHSCOPE_API_KEY`. Keep it outside the repo, preferably in `~/.agent-reach/douyin.env`:

```text
DASHSCOPE_API_KEY=...
```

Current `douyin-mcp-server` supports single video links. Douyin creator profile links should be recorded as `profile_pending_backend` unless the source includes explicit `video_urls`; do not pretend a profile homepage was enumerated when only single-video tools are available.

## Data Layout

Use this project-local layout:

```text
data_social/
  sources/
    social_sources.json
  raw/
    YYYY-MM-DD/
      raw_fetches.jsonl
  extracted/
    YYYY-MM-DD.jsonl
  latest_social_signals.json
  fetch_report_YYYY-MM-DD.json
```

## Extraction Schema

Each extracted signal should include:

- `platform`, `source_name`, `source_url`
- `publish_time`, `fetched_at`, `extracted_at`
- `content_available`, `fetch_status`, `tool_used`
- `mentioned_stocks`, `mentioned_themes`, `mentioned_keywords`
- `core_view`
- `evidence`
- `signal_type`: fact / opinion / sentiment / risk / unknown
- `hard_logic_score`: 0-100
- `emotion_score`: 0-100
- `crowding_risk`: low / medium / high / unknown
- `freshness`: high / medium / low / unknown
- `trade_value`: usable_signal / watch_only / sentiment_only / pending_fetch / ignore
- `risk_notes`
- `usable_for_trading_skills`

## Workflow

1. Register or update sources in `data_social/sources/social_sources.json`.
   - For Douyin creator pages, use `source_type: "profile"` and add `video_urls` when single video links are available.
   - For Douyin single videos, use `source_type: "video"` or omit `source_type`.
   - For Xiaohongshu creators, use `source_type: "profile"` and set `max_notes` for recent-note depth.
2. Run the extractor script:
   `venv/bin/python skills/market_content_extractor/scripts/extract_social_sources.py --sources-json data_social/sources/social_sources.json --output-dir data_social --fetch`
3. Inspect `data_social/fetch_report_YYYY-MM-DD.json`.
4. If `pending_tool_setup` appears, install/configure the missing Agent-Reach channel and rerun.
5. Trading skills should read only `data_social/latest_social_signals.json` or dated files under `data_social/extracted/`.

## Interpretation Rules

Social content is a signal source, not truth.

- Multiple creators discussing the same theme means social attention is rising, not that the stock should be bought.
- Social heat plus news/announcement/market confirmation can strengthen a trading thesis.
- Social heat on a high-position stock can mean crowding and next-day cash-out risk.
- If content has no hard evidence and only emotional wording, mark it as `sentiment_only`.
- If the author is discussing old news, mark freshness lower.
- If a creator names stocks without price, catalyst, or risk, do not treat it as hard logic.
