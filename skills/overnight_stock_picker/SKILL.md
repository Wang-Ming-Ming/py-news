---
name: overnight_stock_picker
description: Use this skill when the user wants a 14:30 A-share overnight stock-picking recommendation: rank five candidate stocks for overnight holding, mark the best one or two for execution, and sell the next morning, combining py-study news data, policy catalysts, market/sector strength, real-time price action, capital flow, and short-term trader discipline.
---

# Overnight Stock Picker

This skill recommends exactly five ranked A-share candidates for an overnight trade: buy near the late session and sell the next morning. The mindset is a top short-term financial analyst and stock trader: find the five stocks with the highest relative probability of next-morning high-open or opening-rush premium, while marking only the best one or two as execution priorities and stating risk and sell discipline.

Do not infer sector leaders from the user's holdings, repeated conversation history, or the user's stated preference. Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current market data: limit-up height, sealing strength, turnover, sector leadership, capital flow, 2-3 day persistence, and policy/news mapping.

## Required Workflow

1. Update or read news first.
   - From the project root, run current news collection when network is available:
     `venv/bin/python main.py --source cls eastmoney_global cninfo ndrc --days 1 --log-level INFO`
   - Then summarize local data:
     `venv/bin/python skills/overnight_stock_picker/scripts/news_snapshot.py --data-dir data_dev --days 7 --limit 80`
   - If crawling fails, still read the latest saved `data_dev` files and clearly state the newest timestamp used.

2. Determine the market style.
   - Check major indices, industry/concept board leaders, market breadth, turnover, and whether funds are attacking growth, policy themes, defensive sectors, or small-cap emotion.
   - Identify the strongest 1-2 tradable themes for tomorrow morning premium.
   - News and policy are catalysts; real money flow and price strength decide the final pick.
   - Before scoring candidates, answer the "overnight three questions": whether the main theme has a next-day relay reason, whether the stock has real divergence support, and whether tomorrow morning is likely to become consensus profit-taking.

3. Build candidates only from the strongest themes.
   - Prefer front-row stocks, high-recognition stocks, sector leaders, comeback leaders, or capacity leaders with visible capital inflow.
   - Use the late-session method as a filter, not as the only reason.
   - At 14:30-14:55, prioritize stocks near the day high, above intraday VWAP/average price, with active turnover and no obvious late-session distribution.
   - Do not recommend sealed limit-up stocks that the user cannot realistically buy.
   - Do not recommend stocks that require a 500K RMB trading-permission threshold, such as STAR Market `688/689` stocks or Beijing Stock Exchange-style restricted tickers. Prefer buyable main-board stocks unless the user explicitly says they can trade those markets.

4. Score candidates using the reference model.
   - Read `references/strategy.md` when detailed scoring or edge cases are needed.
   - Recommend the top five by score, even when the market is weak. Do not end with "do not buy"; instead label confidence and position size.
   - Clearly mark the final execution priority: normally buy only rank 1, or rank 1-2 when both meet the late-session trigger. Ranks 3-5 are watchlist/backup/review candidates.

5. Output in Chinese, concise and decision-oriented.
   - Give exactly five ranked candidate stocks.
   - Include: stock name/code, current price and change, theme, score, recommendation rank, overnight three-question judgment, why it may rise tomorrow morning, suggested position, late-session entry area, and next-morning sell plan.
   - End with the best one or two execution choices, plus ranks 3-5 backup conditions.

## Selection Bias

For this overnight strategy, prefer:

- Same-day strongest theme leaders over isolated individual stocks.
- Stocks with fresh policy/news catalysts plus visible capital inflow.
- Stocks that are strong after 14:30, not only strong in the morning.
- Stocks with 50-500B RMB circulating market cap when possible; smaller is allowed only for clear emotion leaders, larger only for sector capacity leaders.
- Turnover above 5%, volume ratio above 1, active money, and a healthy K-line.

Avoid making a stock the top pick when:

- It is already sealed at limit-up or effectively impossible to enter.
- It requires 500K RMB account permission, including STAR Market `688/689` stocks and Beijing Stock Exchange-style restricted tickers.
- It is only a weak follower while the sector leader is available.
- It has large net outflow, late-session diving, or repeated failed sealing.
- It is a pure social-media concept without real board strength.
- The user already holds too much of the same weak theme and the pick would increase concentration risk.

## Five-Candidate Execution Rule

The five ranks are not five buy orders.

- Rank 1: default execution candidate if it meets the late-session trigger.
- Rank 2: execute only if rank 1 is unavailable, too high, too weak, or if rank 1 and rank 2 are both strong but not overly concentrated.
- Ranks 3-5: backup/watchlist/review candidates; buy only if the top candidates fail and this stock shows clearly better late-session confirmation.
- If all five have low confidence, still rank them but recommend trial-level position only.

## Morning Sell Discipline

The user intends to sell the next morning. Always provide an exit plan:

- High open but cannot continue upward in 5-10 minutes: sell.
- Low open and cannot turn red in 10-15 minutes: sell.
- Rushes near limit-up but cannot seal: sell at least half, often all for this strategy.
- Strong one-word limit-up or fast sealed board: hold only while sealed; open and fail to reseal means sell.

Never promise a stock will rise. Use probability language such as "相对最优", "明早溢价概率更高", and "需要按早盘纪律卖".
