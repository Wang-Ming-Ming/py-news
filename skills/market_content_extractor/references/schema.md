# Social Market Signal Schema

## Source Record

```json
{
  "platform": "douyin",
  "source_name": "Douyin source 1",
  "source_type": "video",
  "source_url": "https://v.douyin.com/...",
  "focus": "recent_trend",
  "notes": "Optional user note"
}
```

For Douyin creator profile links, use:

```json
{
  "platform": "douyin",
  "source_name": "Creator name",
  "source_type": "profile",
  "source_url": "https://v.douyin.com/...",
  "video_urls": [
    "https://v.douyin.com/..."
  ],
  "max_videos": 8,
  "skip_irrelevant": true,
  "focus": "recent_trend"
}
```

If `video_urls` is empty, the current Douyin MCP cannot enumerate homepage works and the fetch status should be `profile_pending_backend`.

## Raw Fetch Record

```json
{
  "platform": "douyin",
  "source_name": "Douyin source 1",
  "source_url": "https://v.douyin.com/...",
  "fetched_at": "2026-06-16T10:00:00+08:00",
  "fetch_status": "success",
  "tool_used": "mcporter:douyin.extract_douyin_text",
  "raw_text": "...",
  "raw_json": {},
  "error": null
}
```

## Extracted Signal

```json
{
  "platform": "douyin",
  "source_name": "Douyin source 1",
  "source_url": "https://v.douyin.com/...",
  "publish_time": null,
  "fetched_at": "2026-06-16T10:00:00+08:00",
  "extracted_at": "2026-06-16T10:00:10+08:00",
  "content_available": true,
  "fetch_status": "success",
  "tool_used": "mcporter:douyin.extract_douyin_text",
  "mentioned_stocks": [],
  "mentioned_themes": ["PCB", "半导体材料"],
  "mentioned_keywords": ["涨价", "订单"],
  "core_view": "Creator says PCB price-rise chain is still active.",
  "evidence": ["mentions PCB price rise", "mentions sector continuation"],
  "signal_type": "opinion",
  "hard_logic_score": 60,
  "emotion_score": 45,
  "crowding_risk": "medium",
  "freshness": "unknown",
  "trade_value": "watch_only",
  "risk_notes": ["Needs confirmation from news and market snapshot"],
  "usable_for_trading_skills": true
}
```
