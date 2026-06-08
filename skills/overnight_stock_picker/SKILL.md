---
name: overnight_stock_picker
description: Use this skill when the user wants a 14:30 A-share overnight stock-picking recommendation: rank five candidate stocks for overnight holding, mark the best one or two for execution, and sell the next morning, combining py-study news data, policy catalysts, market/sector strength, real-time price action, capital flow, and short-term trader discipline.
---

# Overnight Stock Picker

This skill recommends exactly five ranked A-share candidates for an overnight trade: buy near the late session and sell the next morning. The mindset is a top short-term financial analyst and stock trader: find the five stocks with the highest relative probability of next-morning high-open or opening-rush premium, while marking only the best one or two as execution priorities and stating risk and sell discipline.

The core question is: **why would someone buy this stock from the user at a higher price tomorrow morning?** Overnight selection is not about finding the strongest stock today; it is about finding a tradable stock that still has a next-morning buyer story and a realistic high-open/opening-rush path. News and policy provide tomorrow's story, market data confirms whether money already believes it, late-session price action confirms whether funds are willing to hold overnight, and sell discipline captures the premium the next morning.

Do not infer sector leaders from the user's holdings, repeated conversation history, or the user's stated preference. Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current market data: limit-up height, sealing strength, turnover, sector leadership, capital flow, 2-3 day persistence, and policy/news mapping.

The user normally expects to execute one or two stocks each trading day. Still, do not loosen the next-morning premium discipline: always rank five relative candidates and identify the best one or two, but label them trial/watch only when `high_open_score`, `next_day_accept_score`, or fresh-catalyst confirmation is insufficient. Never convert a weak setup into high confidence just because the user plans to buy.

Empirical calibration: for buyable A-share overnight candidates, direct next-morning high-open is uncommon; the more frequent edge is a next-morning opening-rush that must be sold quickly. Separate "gap-open premium" from "opening-rush premium". A candidate can be ranked for trial execution when high-open evidence is modest but opening-rush evidence is strong; in that case explicitly plan for possible low open, repair, rush, and sell.

## Required Workflow

1. Update or read news first.
   - From the project root, run current news collection when network is available:
     `venv/bin/python main.py --source cls eastmoney_global cninfo ndrc --days 1 --log-level INFO`
   - Then summarize local data:
     `venv/bin/python skills/overnight_stock_picker/scripts/news_snapshot.py --data-dir data_dev --days 7 --limit 80`
   - Then generate a market snapshot when AkShare is available:
     `venv/bin/python market_data/market_snapshot.py --mode overnight`
   - Read the latest market snapshot from `data_market/latest_overnight_snapshot.json`.
   - If crawling fails, still read the latest saved `data_dev` files and clearly state the newest timestamp used.

2. Determine the market style.
   - Check major indices, industry/concept board leaders, market breadth, turnover, and whether funds are attacking growth, policy themes, defensive sectors, or small-cap emotion.
   - Identify the strongest 1-2 tradable themes for tomorrow morning premium.
   - News and policy are catalysts; real money flow and price strength decide the final pick.
   - Classify each major theme as one of: not started, early start, confirmed, climax, or fading. Overnight priority is: early start, then confirmed themes with healthy divergence support, then buyable front-row/core stocks before climax. Purely unstarted themes go to watchlist unless the market has begun to confirm them; climax or fading themes must be downgraded unless there is exceptional late-session support.
   - Before scoring candidates, answer the "overnight three questions": whether the main theme has a next-day relay reason, whether the stock has real divergence support, and whether tomorrow morning is likely to become consensus profit-taking.
   - Use `data_market` to confirm all-market行情, board strength, fund flow, limit-up/broken-limit pools, and whether late-session candidates are market-confirmed rather than only news-driven.
   - Today's strong theme is only a candidate source, not a buy reason. Before recommending it, judge whether tomorrow morning is more likely to be continuation, healthy divergence, consensus profit-taking, direct fade, or rotation into a new theme.

3. Build candidates only from the strongest themes.
   - Prefer front-row stocks, high-recognition stocks, sector leaders, comeback leaders, or capacity leaders with visible capital inflow.
   - Do not mechanically map every news item to stocks. Use news to build theme hypotheses, expand only high-impact and market-confirmed themes into candidate pools, and let current market data decide which stocks are leaders, cores, low-position catch-ups, or weak followers.
   - Every candidate must have a concrete next-morning buyer reason: continuing news/policy fermentation, market-recognized theme leadership, buyable substitute when the strongest board is unavailable, healthy divergence support, or late-session fund positioning.
   - Every execution candidate must identify a likely source of tomorrow-morning incremental money. If the answer is only "the sector was strong today", downgrade it to watchlist.
   - Use the late-session method as a filter, not as the only reason.
   - At 14:30-14:55, prioritize stocks near the day high, above intraday VWAP/average price, with active turnover and no obvious late-session distribution.
   - Do not recommend sealed limit-up stocks that the user cannot realistically buy.
   - Do not recommend stocks that require a 500K RMB trading-permission threshold, such as STAR Market `688/689` stocks or Beijing Stock Exchange-style restricted tickers. Prefer buyable main-board stocks unless the user explicitly says they can trade those markets.

4. Score candidates using the reference model.
   - Read `references/strategy.md` when detailed scoring or edge cases are needed.
   - Use `rankings.overnight_candidates` as the market-side candidate pool. Treat `high_open_score` as the primary gate for execution, then use news/policy and late-session tape to confirm.
   - Hard gate: do not mark rank 1-2 as execution priority unless `high_open_score >= 70` and `next_day_accept_score >= 60`, or there is a clearly stated fresh after-hours catalyst strong enough to override the market-side score.
   - When `high_open_score` is below priority but the stock has strong opening-rush evidence, label it as "冲高试错" rather than "高开主推". Strong opening-rush evidence usually requires one or more: previous-limit or strong-pool recognition, same-theme sealed front row that is unavailable, 30B+ RMB amount or clear capacity status, 5%-15% turnover, and a non-climax theme.
   - Recommend the top five by score, even when the market is weak. Do not end with "do not buy"; instead label confidence and position size.
   - If no candidate passes the hard gate, still rank five and name the best relative one or two as trial-only choices; state clearly that the setup lacks priority-grade high-open evidence.
   - Clearly mark the final execution priority: normally buy only rank 1, or rank 1-2 when both meet the late-session trigger. Ranks 3-5 are watchlist/backup/review candidates.

5. Output in Chinese, concise and decision-oriented.
   - Give exactly five ranked candidate stocks.
   - Include: stock name/code, current price and change, theme, score, `high_open_score`, recommendation rank, overnight three-question judgment, tomorrow-morning incremental-money source, why someone may buy it from the user tomorrow morning, suggested position, late-session entry area, and next-morning sell plan.
   - End with the best one or two execution choices, plus ranks 3-5 backup conditions.

## Selection Bias

For this overnight strategy, prefer:

- Same-day strongest theme leaders over isolated individual stocks, but only when tomorrow morning still has a buyer story.
- Stocks with fresh policy/news catalysts plus visible capital inflow, especially when the expectation is not fully priced.
- Early-start themes and confirmed themes with healthy divergence support over unconfirmed imagination or full-consensus climax.
- Stocks that are strong after 14:30, not only strong in the morning.
- Stocks with 50-500B RMB circulating market cap when possible; smaller is allowed only for clear emotion leaders, larger only for sector capacity leaders.
- Turnover around 5%-15%, volume ratio above 1, active money, and a healthy K-line. Turnover above 25% is usually a next-day low-open risk unless it is a clearly successful, market-recognized divergence.
- Capacity or recognition: 30B+ RMB daily amount, previous-limit/strong-pool overlap, or same-theme front row sealed and unavailable.

Avoid making a stock the top pick when:

- It is already sealed at limit-up or effectively impossible to enter.
- It requires 500K RMB account permission, including STAR Market `688/689` stocks and Beijing Stock Exchange-style restricted tickers.
- It is only a weak follower while the sector leader is available.
- It has large net outflow, late-session diving, or repeated failed sealing.
- It is a pure social-media concept without real board strength.
- It has only a news story but no market confirmation, unless it is marked as a watchlist candidate with reduced confidence.
- It is today's hottest stock but tomorrow morning is likely to be pure consensus profit-taking.
- It is too perfectly抢尾盘: close position near the absolute high after a crowded run without fresh catalyst; recent samples show this can be a consensus-profit-taking risk.
- Turnover is above 25% with no clear successful divergence story.
- It is up 7.5%-9.3% and tagged as a hot short-term name, unless the plan explicitly treats it as likely low-open then repair/rush, not direct high-open.
- It is in today's strongest board but has no fresh overnight catalyst, no next-morning incremental-money source, or `high_open_score` below the execution gate.
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
