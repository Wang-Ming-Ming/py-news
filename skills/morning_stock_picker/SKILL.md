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

## Required Workflow

1. Update or read news first.
   - From the project root, run current news collection when network is available:
     `venv/bin/python main.py --source cls eastmoney_global cninfo ndrc --days 1 --log-level INFO`
   - Then summarize local data:
     `venv/bin/python skills/overnight_stock_picker/scripts/news_snapshot.py --data-dir data_dev --days 7 --limit 80`
   - If crawling fails, read the latest saved `data_dev` files and clearly state the newest timestamp used.
   - Filter out news that is later than the user's request time.

2. Determine the likely morning market style.
   - Before 9:15: use prior-day close, prior-day涨停复盘, sector strength, overnight overseas markets, commodities, policy, company announcements, and morning news.
   - During auction: add auction涨幅, auction volume, one-word limit-up status, weak-to-strong behavior, and whether the strongest theme is being confirmed.
   - After 9:30: add open, early分时承接, sector breadth, active money, and whether the candidate is above its intraday average price.
   - Before selecting stocks, classify yesterday's strongest themes as continuation, healthy divergence, or fade/rotation risk. Do not simply buy yesterday's strongest sector again without this check.

3. Build a full-market candidate pool.
   - Start from the whole A-share market and all sectors, then filter by the user's tradability rules.
   - Prefer stocks in the strongest 1-3 themes, with high recognition, company-level catalysts, prior-day money traces, or clear policy/news mapping.
   - Recommend exactly five ranked candidates, but mark the best 1-2 as the only execution priorities.
   - If the strongest stock is sealed limit-up or not realistically buyable, use it only as a sector flag and recommend a buyable same-theme alternative.

4. Apply hard filters.
   - By default, do not recommend ChiNext/Growth Enterprise Market stocks such as `300/301` tickers, unless the user explicitly asks to include them.
   - Do not recommend stocks requiring a 500K RMB permission threshold, such as STAR Market `688/689` stocks or Beijing Stock Exchange-style restricted tickers, unless the user explicitly says they can trade them.
   - Avoid ST, delisting-risk, major negative公告, obvious fraud/regulatory-risk, or severe减持 pressure.
   - Avoid one-word sealed limit-up stocks as final buy recommendations because the user cannot realistically enter.
   - Avoid pure social-media concepts without news/policy/board strength support.
   - Avoid prior-day blow-off distribution, large bearish candle with heavy volume, or candidates with obvious sell-off risk unless the plan is explicitly a weak-to-strong reversal setup.

5. Score candidates.
   - Read `references/strategy.md` when detailed scoring, auction logic, or output rules are needed.
   - Rank by score and practical tradability, not by theoretical涨停 probability alone.

6. Output in Chinese, concise and decision-oriented.
   - Include the data scope: live latest data or the explicit historical cutoff used.
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
