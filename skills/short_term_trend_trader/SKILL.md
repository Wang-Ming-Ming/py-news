---
name: short_term_trend_trader
description: Use this skill when the user wants A-share short-term trend trading or position management over several trading days: decide what to buy, hold, add, reduce, or sell based on latest news, one-week message flow, market/sector strength, trend health, capital acceptance, and strict turn-weak sell discipline. This is for swing-like short-term trades, not same-day scalping or one-night-only overnight trades.
---

# Short-Term Trend Trader

This skill handles the user's new short-term mode: hold a strong stock for several trading days while the trend and thesis remain intact, and sell when the trend turns weak. The mindset is a top financial analyst plus elite short-term trend trader.

The core question is: **is this stock still in a tradable short-term uptrend with a valid reason for funds to keep buying over the next 1-5 trading days?**

This is not a promise of profit. Use probability language such as "趋势仍健康", "转弱信号未出现", "只适合小仓试错", "跌破关键位就退出", and "不满足触发条件不买".

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
2. Theme and industry-chain strength confirmed by market data.
3. The stock's own trend: higher lows, moving-average support, volume quality, VWAP/average-price behavior, and relative strength.
4. Capital acceptance: repeated pullback absorption, afternoon/late-session support, and lack of heavy distribution.
5. Clear sell discipline: once the trend turns weak, exit without arguing with the tape.

Do not recommend based on the user's holdings, historical chat, or preference. For new ideas, scan the full tradable market. For holding analysis, evaluate the user's positions first, but do not defend them just because the user owns them.

## Data Workflow

Before analysis, use the newest valid local data available:

1. Read/update news when network is available:
   `venv/bin/python main.py --source cls eastmoney_global cninfo ndrc --days 7 --log-level INFO`
2. Summarize local news:
   `venv/bin/python skills/overnight_stock_picker/scripts/news_snapshot.py --data-dir data_dev --days 7 --limit 120`
3. Read social market signals when available:
   `data_social/latest_social_signals.json`
4. Read Serenity hard-logic research cache when available:
   - `data_research/serenity/latest_watchlist.json`
   - `data_research/serenity/latest_report.md`
   - `data_research/serenity/rejected_candidates.md`
   Treat it as supplemental knowledge, not a closed universe. It helps identify hard-logic trend names and rejected weak logic, but every recommendation must still pass full-market trend and capital confirmation.
5. Read the latest valid market snapshot:
   - Prefer `data_market/latest_custom_snapshot.json` if it is the freshest valid file.
   - Otherwise use `data_market/latest_morning_snapshot.json` or `data_market/latest_overnight_snapshot.json`.
   - Never use failed snapshots or `stock_count=0` as market truth.
6. Review recent market history when available: the latest 3-7 trading days under `data_market/YYYY-MM-DD/` and any `data_market/research/` files.

If fresh data collection fails, use the latest saved files and clearly state the data timestamp.

## Full-Market Selection

For new buys, do not start from `rankings.overnight_candidates` or `rankings.active_candidates`. Candidate pools can overfit today's active stocks and miss hard-logic trend stocks before ignition.

Build candidates in this order:

1. Extract one-week hard themes: policy, company公告, orders, price rises, supply-demand shifts, overseas mapping, industry events, and social attention only as secondary evidence.
2. Map themes to industry-chain nodes and all tradable A-share stocks.
3. Filter by tradability: default exclude STAR Market `688/689`, Beijing Stock Exchange-style restricted names, ST/delisting risk, and names requiring 500K RMB permission. Keep caution on `300/301` unless the user allows them.
4. Evaluate trend health and position: early trend, confirmed trend, acceleration, healthy pullback, climax, or broken trend.
5. Validate with current market data: sector strength, leader confirmation, turnover, fund flow, limit-up anchors, relative strength, and recent support.

## Bottleneck Research Gate

This skill should use `serenity-bottleneck` as the main hard-logic research companion, especially for several-day trend trades.

The stock universe remains full-market. The bottleneck pass is used to decide whether a trend stock has a real industrial reason to keep attracting funds, not to create a closed list.

If `data_research/serenity/latest_watchlist.json` exists, use it as a hard-logic supplement after reading the one-week news flow and before final trend ranking. Do not rank only this file. Merge its names with full-market trend candidates confirmed by price, volume, sector behavior, and fund path.

Trend trading can hold future expectations before earnings are confirmed. Classify each Serenity-related trend stock:

- `current_hard_logic`: current business/order/revenue/price evidence exists.
- `future_expectation`: validation, sample, capacity, customer import, price-rise, or order expectation exists and the tape confirms funds are pricing it.
- `pure_concept`: only label similarity or explicit company denial.

Do not delete `future_expectation` stocks only because orders are not yet visible. They can be bought/held for several days when the theme is still fermenting and the trend is healthy. However, if they lose trend support or fresh announcements kill the expectation, sell quickly because there is no current earnings cushion.

Workflow:

1. Start with one-week message flow and full-market stock data.
2. For supply-chain themes, apply Serenity-style analysis: anchor the event, draw the chain, find the scarce node, identify direct beneficiaries, and reject loose concept followers.
3. Build a hard-logic trend watchlist from the bottleneck result: direct beneficiaries, capacity cores, pre-ignition trend stocks, and low-/middle-position extensions.
4. Merge that watchlist with market-confirmed trend names from the full market.
5. Rank only after trend health, capital acceptance, price position, announcement risk, and invalidation levels are checked.

A stock can be held or bought for several days only when both sides agree: the industrial thesis is still alive and the trend tape has not broken. If the bottleneck thesis is strong but the trend breaks, sell. If the chart is strong but the business/chokepoint logic is weak, downgrade to technical speculation.

For future-expectation trades, the industrial thesis means "expectation still has room to be repriced", not "orders have already landed". Track whether the next verification step is approaching and whether money is still accumulating.

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
