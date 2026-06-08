---
name: morning_stock_picker
description: Use this skill when the user asks for a pre-market or opening-session A-share stock-picking plan, usually around 8:40-9:30 China time: recommend five ranked stocks for short-term intraday/early-session trading using py-study news, policy catalysts, prior-day market data, available auction/opening data, and top short-term trader discipline.
---

# Morning Stock Picker

This skill builds a morning A-share trading plan. The mindset is a top financial analyst plus elite short-term stock trader: identify the five stocks with the highest relative probability of being attacked by active funds after the open, then give concrete execution conditions.

The recommendation is a trading plan, not a promise. Use probability language such as "相对最优", "更容易被资金攻击", "竞价确认后再执行", and "不满足条件就放弃".

## Highest Priority Rule

For live trading analysis, use the latest valid data available while the analysis is being performed, as long as it is relevant to the decision. Do not ignore newly available auction, opening, market, or news data merely because it appeared after the first user message in the same live request.

- If the user asks in a live morning session before 9:15, use the latest news, policy,公告, overnight market, and prior-day market data available at analysis time. There is normally no auction data yet.
- If auction data becomes available during analysis, it may be used and should be clearly labeled.
- If opening data becomes available during analysis, it may be used and should be clearly labeled.
- Only enforce a hard historical cutoff when the user explicitly says the scenario is a replay,假设, backtest, or "只使用某时间之前的数据".
- Never use future or unavailable data in a historical replay.

Do not infer sector leaders from the user's holdings, repeated conversation history, or the user's stated preference. Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current market data: limit-up height, sealing strength, turnover, sector leadership, capital flow, 2-3 day persistence, and policy/news mapping.

The user may expect to buy one or two stocks from the morning plan. Still, do not loosen execution standards: rank five relative candidates and identify the best one or two, but label them watch/trial only when news strength, market confirmation, auction/opening confirmation, or risk-reward is insufficient. Never turn a weak setup into a high-confidence recommendation just because the user plans to trade.

## Message-First Morning Logic

Morning stock picking must be message-first, not yesterday-strength-first. Start from today's newest available catalysts, then map them into themes, industry chains, and tradable stocks.

The first anchor must be today's fresh message flow:

- 最新新闻
- 政策
- 公司公告
- 外围市场
- 商品、汇率、利率
- 产业事件
- 公司级硬催化

Prior-day market action is only validation, not the recommendation anchor. Use yesterday's data to judge capital traces, recognition, liquidity,兑现 pressure, climax, fade, divergence, or退潮. Never assume a sector will continue today just because it was strong yesterday.

Candidate generation order:

1. Build today's message-theme map from fresh news, policy, announcements, overseas markets, commodities, FX/rates, industry events, and company catalysts.
2. Map those themes to industry-chain nodes and related A-share stocks across the whole market.
3. Use prior-day market data only to validate whether funds already have a base:辨识度,成交额,涨停/炸板, sector breadth, capital flow, and兑现 pressure.
4. Use auction/opening data as final confirmation when available.
5. Output exactly five candidates, then identify only the best 1-2 as execution priorities.

If today's fresh message conflicts with yesterday's strong sector, respect today's new message first. Yesterday's strength becomes a risk check only. Unless 9:15 auction or 9:30 opening data clearly confirms yesterday's main line is still strengthening, do not force recommendations into yesterday's strong direction.

Recommendations must come from the full market and current real data:

- Do not recommend based on the user's holdings.
- Do not recommend based on stocks repeatedly mentioned in historical chat.
- Do not cater to the user's subjective preference.
- Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current data, not assumed.

## Required Workflow

1. Update or read news first.
   - From the project root, run current news collection when network is available:
     `venv/bin/python main.py --source cls eastmoney_global cninfo ndrc --days 1 --log-level INFO`
   - Then summarize local data:
     `venv/bin/python skills/overnight_stock_picker/scripts/news_snapshot.py --data-dir data_dev --days 7 --limit 80`
   - Then generate a market snapshot when AkShare is available:
     `venv/bin/python market_data/market_snapshot.py --mode morning`
   - Read the latest market snapshot from `data_market/latest_morning_snapshot.json`.
   - If crawling fails, read the latest saved `data_dev` files and clearly state the newest timestamp used.
   - Filter out news that is later than the user's request time.

2. Build today's message-theme map.
   - Start with today's newest valid news, policy, company announcements, overseas markets, commodities, FX/rates, industry events, and company-level hard catalysts.
   - Group messages by theme and grade them by freshness, hardness, market scope, company specificity, and whether they can change expectations today.
   - Map each strong message theme to industry-chain nodes and related stocks across the whole market.
   - Do not start by asking which sector was strongest yesterday.

3. Determine the likely morning market style and validate with prior-day data.
   - Before 9:15: use prior-day close, prior-day涨停复盘, sector strength, overnight overseas markets, commodities, policy, company announcements, and morning news.
   - During auction: add auction涨幅, auction volume, one-word limit-up status, weak-to-strong behavior, and whether the strongest theme is being confirmed.
   - After 9:30: add open, early分时承接, sector breadth, active money, and whether the candidate is above its intraday average price.
   - Before selecting stocks, classify yesterday's strongest themes as continuation, healthy divergence, or fade/rotation risk. This is a validation step only, not the anchor.
   - If today's message flow points to a new theme while yesterday's strong theme lacks fresh catalysts, prefer the new message theme unless auction/opening confirms yesterday's line.
   - Use `data_market` to confirm all-market行情, industry/concept strength, fund flow, limit-up/broken-limit pools, and tradable candidate rankings.

4. Build a full-market candidate pool.
   - Start from the whole A-share market and all sectors, then filter by the user's tradability rules.
   - Prefer stocks mapped from today's strongest message themes, with high recognition, company-level catalysts, prior-day money traces, or clear policy/news mapping.
   - Recommend exactly five ranked candidates, but mark the best 1-2 as the only execution priorities.
   - If the strongest stock is sealed limit-up or not realistically buyable, use it only as a sector flag and recommend a buyable same-theme alternative.

5. Apply hard filters.
   - By default, do not recommend ChiNext/Growth Enterprise Market stocks such as `300/301` tickers, unless the user explicitly asks to include them.
   - Do not recommend stocks requiring a 500K RMB permission threshold, such as STAR Market `688/689` stocks or Beijing Stock Exchange-style restricted tickers, unless the user explicitly says they can trade them.
   - Avoid ST, delisting-risk, major negative公告, obvious fraud/regulatory-risk, or severe减持 pressure.
   - Avoid one-word sealed limit-up stocks as final buy recommendations because the user cannot realistically enter.
   - Avoid pure social-media concepts without news/policy/board strength support.
   - Avoid prior-day blow-off distribution, large bearish candle with heavy volume, or candidates with obvious sell-off risk unless the plan is explicitly a weak-to-strong reversal setup.

6. Score candidates.
   - Read `references/strategy.md` when detailed scoring, auction logic, or output rules are needed.
   - Rank by message-first score and practical tradability, not by theoretical涨停 probability alone.
   - New message > old strength. Prior-day strength can lift confidence only after today's message and auction/opening logic are valid.
   - If no candidate reaches execution quality, still give five ranked relative candidates, but state that the best 1-2 require small trial position, auction confirmation, or no trade if the trigger fails.

7. Output in Chinese, concise and decision-oriented.
   - Include the data scope: live latest data or the explicit historical cutoff used.
   - Include today's main message themes and their stock mapping.
   - Include the continuation/divergence/fade judgment for yesterday's strongest themes.
   - Give exactly five ranked stocks.
   - For each stock include: stock name/code, reference price/current available price, theme, score, reason, auction/opening condition, buy trigger, abandon condition, and position size.
   - End with the final execution priority: "只重点买第几名/哪两只", plus the key no-buy conditions.

## Morning Execution Logic

Do not only chase high opens.

- 高开 2%-6%: standard strong setup; buy only if auction volume and opening承接 confirm.
- 高开 7%-9%: high兑现 risk; do not chase unless sector is extremely strong and the stock quickly seals or holds承接.
- 一字涨停 or sealed limit-up: sector flag only; not a final buy recommendation.
- 平开/小高开 0%-2%: acceptable when news is hard and the stock quickly放量上攻.
- 小低开 -1% to -3%: not automatically bad; buy only if it quickly turns red-to-green with sector confirmation.
- 大低开 below -4%: default abandon unless there is a very strong catalyst and fast repair.

## Position Discipline

- Morning plans should not imply full position.
- Normally recommend 1-2 execution stocks from the five, with small-to-medium position per stock.
- If market style is weak or candidates are mainly high-open兑现 setups, lower position size.
- If the user already holds related stocks, mention concentration risk and avoid adding too much of the same weak theme.

## Sell Discipline

For short-term morning trades, always include an exit mindset:

- High open then cannot continue upward in 5-10 minutes: reduce or sell.
- Opens strong but breaks intraday average price with volume: reduce or sell.
- Weak-to-strong setup fails to turn red within 10-15 minutes: abandon or cut.
- Rushes near limit-up but cannot seal: take profit on at least part of the position.
- Strong sealed board: hold only while封单 stable; open and fail to reseal means sell.
