---
name: short_term_trend_trader
description: 'Use this skill when the user wants A-share short-term trend trading or position management over several trading days: decide what to buy, hold, add, reduce, or sell based on latest news, one-week message flow, market/sector strength, trend health, capital acceptance, and strict turn-weak sell discipline. This is for swing-like short-term trades, not same-day scalping or one-night-only overnight trades.'
---

# Short-Term Trend Trader

This skill handles the user's new short-term mode: hold a strong stock for several trading days while the trend and thesis remain intact, and sell when the trend turns weak. The mindset is a top financial analyst plus elite short-term trend trader.

The core question is: **is this stock still in a tradable short-term uptrend with a valid reason for funds to keep buying over the next 1-5 trading days?**

This is not a promise of profit. Use probability language such as "趋势仍健康", "转弱信号未出现", "只适合小仓试错", "跌破关键位就退出", and "不满足触发条件不买".

## Objective Server Data Boundary

The server has no AI and supplies objective data only. It must not determine trend state, announcement risk, catalyst relevance, candidates, or trades. At the start of analysis run:

`venv/bin/python skills/short_term_trend_trader/scripts/server_context.py`

This sync is mandatory and must be the first data action even when a local cache already exists. Connection settings resolve from process `STOCK_DATA_SERVER`/`STOCK_DATA_TOKEN`, then the repository-root `.env`, then the legacy `~/.config/stock-data-client/config.json`. All three stock skills share the single `data_server_cache` directory and `data_server_cache/latest_context.json`; never create a skill-specific objective-data cache. Verify health/calendar/snapshot time, expected counts, `sync_duration_seconds`, `using_cached_data`, and that the context `mode` matches this run, then query objective multi-day fields and fetch relevant original news/announcement text by ID. Keep all trend, thesis, risk, and position decisions in Codex. If the server is unavailable, use a complete local cache only with an explicit timestamp warning.

## Strategy Boundary

- This is a several-day short-term trend strategy, usually 2-7 trading days.
- It is not the morning `buy after auction and sell quickly` mode.
- It is not the overnight `buy near close and sell next day` mode.
- It can recommend holding after a profitable day if the trend is still healthy.
- It can recommend selling before a day ends if price action proves the trend is broken.
- It must not mechanically hold every red/up day or sell every green/down day. In A-shares, red means up and green means down; day color is a warning signal, not the whole strategy.

## Required Mindset

Prioritize hard logic plus trend health:

1. Message flow over at least the latest week, not only today's headline.
2. Theme strength and stock relevance confirmed by market data and direct public evidence.
3. The stock's own trend: higher lows, moving-average support, volume quality, VWAP/average-price behavior, and relative strength.
4. Capital acceptance: repeated pullback absorption, afternoon/late-session support, and lack of heavy distribution.
5. Clear sell discipline: once the trend turns weak, exit without arguing with the tape.

Do not recommend based on the user's holdings, historical chat, or preference. For new ideas, scan the full tradable market. For holding analysis, evaluate the user's positions first, but do not defend them just because the user owns them.

## Data Workflow

Before analysis, use the newest valid server-backed local cache available:

1. Run `venv/bin/python skills/short_term_trend_trader/scripts/server_context.py` and verify the resulting context, health, calendar, and snapshot version.
2. Use only the server-backed news/announcement indexes under `data_server_cache` and fetch relevant original text by ID. Do not run local collectors or read `data_dev`.
3. Read social market signals when available:
   `data_social/latest_social_signals.json`
4. Read the latest valid snapshot, features, and pools referenced by `data_server_cache/latest_context.json`; never use legacy local `data_market` files.
5. Review recent objective market history only from `data_server_cache/archive/YYYY-MM-DD/market/`.

If server sync fails, use only the latest complete context already under `data_server_cache`, clearly state its timestamp and age, and lower confidence when stale.

## Full-Market Selection

For new buys, do not start from `rankings.overnight_candidates` or `rankings.active_candidates`. Candidate pools can overfit today's active stocks and miss hard-logic trend stocks before ignition.

Build candidates in this order:

1. Extract one-week hard themes: policy, company公告, orders, price rises, supply-demand shifts, overseas mapping, industry events, and social attention only as secondary evidence.
2. Search all tradable A-share stocks for directly named companies, verified business beneficiaries, and market-recognized theme leaders or low-position candidates.
3. Filter by tradability: default exclude STAR Market `688/689`, Beijing Stock Exchange-style restricted names, ST/delisting risk, and names requiring 500K RMB permission. Keep caution on `300/301` unless the user allows them.
4. Evaluate trend health and position: early trend, confirmed trend, acceleration, healthy pullback, climax, or broken trend.
5. Validate with current market data: sector strength, leader confirmation, turnover, fund flow, limit-up anchors, relative strength, and recent support.

## Direct-Evidence Boundary

Do not load optional industry-research resources or perform upstream/downstream or scarcity inference during a normal trend recommendation. Those resources and data remain stored but are intentionally disabled until separately improved.

For candidate relevance, use only original announcements, reliable reports that name the company, verified public company business facts, and current market recognition. Expectation trades remain eligible when labeled honestly and confirmed by trend, volume, and theme behavior; loose concepts or company-denied stories are rejected.

Check issuer official news, investor interactions, or event notices only when the server feed is insufficient for a leading candidate. Do not reverse-map upstream/downstream peers from an anchor stock.

## Holding Decisions

When the user provides holdings, evaluate each position as:

- `继续持有`: thesis valid, sector not broken, price above key trend support, no distribution.
- `减仓`: trend still alive but near climax, heavy divergence, high gap, or concentration risk.
- `清仓/卖出`: hard break of trend, negative announcement, sector fade, heavy-volume down move, or original thesis invalidated.
- `不加仓`: holding can remain, but new money should wait for confirmation.
- `可加仓`: only after profit cushion and new confirmation; never add to a falling broken trend.

Always give concrete prices or zones when market data supports them: key support, invalidation level, add-on trigger, and sell zone.

## Trend Health Rules

Read `references/strategy.md` for detailed scoring, trend-state definitions, buy/hold/sell gates, and output templates.

Core rules:

- Hold while the stock remains above its key trend support, theme remains valid, and pullbacks are absorbed.
- Do not hold a stock just because it was strong yesterday if today's trend breaks.
- Do not sell a normal low-volume pullback if the stock remains above support and the theme is still strengthening.
- Sell or reduce when price breaks key support with volume, loses sector status, shows distribution, or the catalyst is invalidated.
- A profitable stock can be held several days, but every day must re-earn the right to be held.

## Output Requirements

For a short-term trend stock-picking request, output in Chinese:

1. Data scope and market regime.
2. The strongest one-week message themes and current funding path.
3. Exactly five ranked candidates from the full market.
4. For each: stock/code, theme, current/reference price, trend state, reason, buy trigger, hold condition, sell/abandon condition, position suggestion, expected holding window.
5. Final focus: only the best 1-2 candidates. If confidence is weak, say only observe or small trial.

For a holding-management request, output:

1. Overall account risk and theme concentration.
2. Each holding: `留/减/卖/加` decision, reason, key price, intraday/tomorrow plan.
3. Which holding is strongest, which should be sold first, and whether any new buy is better than existing holdings.

Never turn a weak trend into a high-confidence recommendation. If no clean trend setup exists, say so directly.
