---
name: overnight_stock_picker
description: Use this skill when the user wants a 14:30 A-share overnight stock-picking recommendation: rank seven candidate stocks for overnight holding, including five main candidates plus one quiet ignition candidate and one low-position acceptance candidate from the strongest limit-up logic, mark the best two or three for execution when conditions are hard enough, and sell during the next trading day, combining py-study news data, policy catalysts, market/sector strength, real-time price action, capital flow, and short-term trader discipline.
---

# Overnight Stock Picker

This skill recommends exactly seven ranked A-share candidates for an overnight trade: buy near the late session and sell during the next trading day. The mindset is a top short-term financial analyst and stock trader: find five main candidates with the highest relative probability of next-day upside premium, plus one quiet ignition candidate and one low-position acceptance candidate from the day's strongest limit-up logic. Mark the best two or three as execution priorities only when conditions are hard enough, and state risk and sell discipline.

The core question is: **why would someone buy this stock from the user at a higher price tomorrow, and in which time window?** Overnight selection is not about finding the strongest stock today; it is about finding a tradable stock that still has a next-day buyer story and a realistic premium path. News and policy provide tomorrow's story, market data confirms whether money already believes it, late-session price action confirms whether funds are willing to hold overnight, and sell discipline captures the premium on the next trading day.

## Trading Calendar Gate

Before any overnight recommendation, confirm the next A-share trading day. Do not assume the next calendar day is tradable. Check the current date, weekday, weekend, exchange holiday schedule, and any known special market closure. In the output, state the exact next trading day when the trade will be sold.

Calendar confirmation must come from a reliable trading-calendar source: prefer an exchange holiday notice or a valid local/API A-share trade calendar, and use weekday inference only as a final consistency check. Record the current date, the last completed trading day, the exact next trading day, and the number of non-trading nights carried. If the next trading day cannot be confirmed, do not issue an executable overnight recommendation, buy range, or normal position size; provide a research-only watchlist and state that calendar confirmation is missing.

If the next calendar day is not a trading day, the setup is no longer a normal one-night overnight trade. Treat it as a cross-weekend or cross-holiday inventory trade:

- replace "tomorrow" with "next trading day" and use the exact date when possible;
- reduce confidence and position size because the user must carry extra nights of announcement, policy, overseas-market, commodity, exchange-rate, and sentiment risk;
- require a harder buyer story that can survive the closure period, such as a multi-day hard main line, still-fermenting policy/industry catalyst, confirmed capacity core, or unavailable front-row substitution demand;
- downgrade crowded high-gain stocks, late-session抢筹, high-position distribution, and pure emotion even more aggressively, because no next-morning liquidity exists to exit quickly;
- avoid making rank 1-2 execution picks unless their next-trading-day red/positive exit probability remains strong after the extra holding period;
- if the market is weak or the trade depends on immediate next-morning momentum, say clearly that the plan is not suitable for a normal position and only allows tiny trial size or no trade.

For holiday/weekend gaps, the key question becomes: **who will still want to buy this stock on the next trading day after several non-trading days, and what holiday-period news path can keep the story alive?**

## Primary Objective: Red-Exit Probability

For this user, the first objective of rank 1-2 is not theoretical upside or limit-up imagination. It is the probability that tomorrow gives a tradable **red/positive exit window**: a high open, opening rush, red-to-green repair, or intraday continuation above the late-session cost area. A pick that may be conceptually correct but is likely to open weak and never give a red exit is a bad overnight recommendation for this strategy.

Use this priority order for rank 1-2:

1. Probability of a next-day red exit window.
2. Clarity of tomorrow's incremental buyer source.
3. Freshness and hardness of the catalyst.
4. Quality of late-session acceptance.
5. Upside imagination such as next-day limit-up probability.

Before marking rank 1 or rank 2 as executable, explicitly answer:

- Where is the most likely red exit window tomorrow: open, first 30 minutes, late morning repair, or afternoon continuation?
- Why would tomorrow's buyers still need to buy after today's close instead of selling into the open?
- What would make the stock fail to provide a red exit, and where should the user abandon quickly?

If rank 1-2 cannot answer these questions, label the setup as observation/trial only even if the stock has a strong story. Do not make a stock the top execution pick only because it has the largest next-day limit-up imagination.

Do not infer sector leaders from the user's holdings, repeated conversation history, or the user's stated preference. Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current market data: limit-up height, sealing strength, turnover, sector leadership, capital flow, 2-3 day persistence, and policy/news mapping.

The user normally buys one or two stocks from the morning plan, because morning trades can use fresh-message and auction/opening confirmation. Overnight is different: the user may buy two or three stocks from the late-session plan, including rank 6 or rank 7 when they are high-quality. Still, do not loosen the next-day premium discipline: always rank seven relative candidates and identify the best two or three, but label them trial/watch only when next-day buyer logic, fresh-catalyst confirmation, late-session acceptance, or market validation is insufficient. Never convert a weak setup into high confidence just because the user may buy three stocks.

Empirical calibration: for buyable A-share overnight candidates, direct next-morning high-open is uncommon; the more frequent edges are opening-rush, low-open repair, and confirmed intraday continuation. Separate "gap-open premium", "opening-rush premium", "low-open repair", and "intraday-continuation premium". A candidate can be ranked for trial execution when high-open evidence is modest but repair/continuation evidence is strong; in that case explicitly plan for possible low open, repair, rush, continuation confirmation, and sell.

Recent failure calibration: a good next-day broad market does not save a bad overnight stock. Overnight picks must predict the next-day capital path, not merely whether the market may be red or green. A defensive/cyclical pick can fail in a risk-on repair market, and a hot theme can fail when it becomes consensus inventory waiting to be sold. Rank 1-2 must therefore match the likely next-day money path, not just today's late-session strength.

Do not mechanically ban large-gain stocks. A large-gain stock can still be an overnight candidate when it is a true capacity core, the theme is still in early/confirmed stage, front-row stocks are unavailable, late-session acceptance is healthy, and tomorrow has clear incremental buyers. However, a large-gain stock must pass a higher cash-out bar: if the move is old-news, crowded, late-pumped, high-turnover exhaustion, or lacks fresh next-day buyer demand, downgrade it even if it looks strong today.

## Next-Day Exit Window, Not Only Morning

The user's overnight trade is a one-night holding trade: buy near today's close and sell no later than the next trading day. The default expectation is still to realize profits early, but the skill must not assume the user must sell only in the morning. A good overnight candidate can be:

- high-open and sell quickly;
- flat or small-low open, then repair and rush;
- morning divergence, then trend continuation into late morning or afternoon;
- sector-core continuation where the best sell point appears after the opening noise.

Therefore selection must optimize for **next-day upside premium**, not only next-morning gap premium. When scoring rank 1-2, judge whether the stock has a realistic chance to be one of tomorrow's strongest tradable names, and specify the expected premium window: open, first 30 minutes, late morning, afternoon continuation, or low-open repair.

Do not let this become a reason to hold losers. If the stock cannot hold its key price, loses VWAP with sector weakening, or the original buyer story is invalidated, exit early. Holding past the morning is allowed only when the stock and sector keep confirming the thesis.

## Morning vs Overnight Boundary

Do not copy the morning skill's selection logic directly. Morning selection is message-first and uses fresh news, auction, and opening confirmation. Overnight selection must still respect news, but the edge more often comes from late-session market data, trend structure, acceptance, and the trader's ability to infer tomorrow's capital path before it becomes obvious.

For overnight:

- News is a catalyst, not enough by itself.
- Market acceptance and trend structure are primary filters.
- A quiet, stabilized hard-logic stock can be better than an obvious hot stock when tomorrow's discovery path is clearer.
- A strong limit-up stock is often an anchor, not the execution pick; use it to find buyable same-chain low-position acceptance candidates.
- The final output should help the user choose 1-3 overnight positions, with the third position usually coming from a true rank 6 or rank 7 setup.

## Timing and Data-Depth Discipline

Do not hard-code the recommendation to 14:50 or wait passively for 14:55. When the user asks for a late-session recommendation, start the analysis immediately with the latest valid market and news data available. If the user asks around 14:30, spend the necessary time reading data and thinking, but aim to deliver the actionable recommendation around 14:45-14:50 and preferably no later than 14:52. The final minutes are for cancellation/risk checks, not for starting the analysis.

If fresh data collection is slow or partially failing, do not delay past the user's execution window. Use the newest valid snapshot, clearly state its timestamp and any missing endpoints, and combine it with local historical market data. A slightly older valid all-market snapshot is better than a late answer that arrives after the user can no longer act.

Market data is a hard requirement for overnight recommendations. Before ranking, read enough market data to understand the whole market, not just a few familiar stocks:

- latest valid all-market `raw.stock_spot` for prices, gains, amount, high/low position, and late-session status;
- concept/industry boards and fund-flow data when available;
- limit-up, broken-limit, strong, previous-limit, and DTGC pools for theme anchors and risk;
- recent local snapshots under `data_market/YYYY-MM-DD/` to compare today's theme, breadth, limit-up quality, and candidate behavior across multiple trading days;
- research files under `data_market/research/` such as `all_a_kline_*.jsonl`, `daily_pool_tags_*.json`, and overnight research summaries when they are available and relevant.

Multi-day market data is mandatory, not optional. The latest snapshot tells whether the stock is executable now; the last several trading days tell whether the theme is truly becoming a main line, quietly accumulating, rotating, climaxing, or fading. Do not make an overnight recommendation from only the newest market snapshot unless older local data is unavailable; if it is unavailable, say so clearly and lower confidence.

When local data exists, review at least the most recent 3 trading days, preferably 5-7 trading days when time permits. Compare:

- whether the same theme has appeared repeatedly in board strength, limit-up pools, amount rankings, or strong-pool composition;
- whether the candidate has higher lows, repeated late-session acceptance, controlled pullbacks, or steady volume rather than a one-day spike;
- whether leaders are progressing from early start to confirmation, or moving from climax into cash-out risk;
- whether low-position candidates are newly recognized or only weak followers of an already exhausted theme.

Use historical data to judge whether a stock is truly stabilizing, quietly trending, or merely bouncing weakly. Use current late-session data to decide whether the idea is executable today.

## Elite Overnight Execution Rules

For the user's main style, the late-session trade is a one-night inventory trade. The goal is not to own the strongest stock at the close; it is to own something that other traders may still want to buy tomorrow.

Apply these hard rules before naming execution priorities:

1. Next-day buyer logic is the first gate. A candidate must answer who may buy it tomorrow and why: fresh evening/overnight catalyst, front-row sealed-unavailable substitution, recognized capacity core, healthy divergence repair, or a theme still in early/confirmed stage. "It was strong today" is not enough.
2. Determine the next-day capital path before ranking stocks: risk-on repair, risk-off defense, same-theme continuation, consensus cash-out, or rotation into fresh news. Broad-market strength only changes risk appetite; it does not validate a stock unless the stock belongs to the actual money path. If risk-on repair is likely, downgrade defensive/coal/high-dividend picks; if risk-off is likely, downgrade high-beta technology and crowded emotion.
3. Rank 1-2 are the default execution names, so their bar is higher than the general candidate pool. Rank 6 and rank 7 can also become execution names when their special setup is stronger than ranks 3-5. Do not put a soft candidate into the execution combination unless it is explicitly labeled trial/watch and the output says there is no priority-grade overnight trade.
4. Confirm late-session acceptance in the user's real execution window. If the user asks around 14:30-14:45, analyze immediately and provide the actionable ranking as soon as the market/news read is sufficient, preferably before 14:52. Do not wait for 14:55 or the close. Use 14:55 only as a final cancellation/sanity check: if the stock or theme suddenly dives, loses VWAP, or shows fake-pull behavior, cancel the buy.
5. Today's strong theme can still be tomorrow's seller inventory, especially in the morning. Before promoting a same-day strong theme, decide whether it is early/confirmed continuation, healthy divergence, or crowded consensus cash-out.
6. Label the premium type for every candidate: gap-open premium, opening-rush premium, low-open repair, intraday-continuation premium, or consensus-profit-taking risk. The next-day sell plan must match this label.
7. Weak markets automatically reduce execution. When breadth is poor, only rank 1 can normally be executed; rank 2 must be clearly independent or much stronger. Rank 6 or rank 7 can enter the buy plan only when its catalyst path is independent and stronger than the general market.
8. Announcement risk is a hard filter. Check company公告, after-hours risk, reduction plans, abnormal-move notices, clarification notices, regulatory letters, and performance risks before recommending a short-term hot stock for overnight. A post-close clarification, reduction, abnormal-move notice, or risk notice cancels the setup even if the late-session tape looked strong.
9. The buy plan and next-day sell script are one trade. If the sell script is unclear, the buy recommendation is incomplete.

## Research Rank vs Execution Rank

Separate the candidate list from the actual buy list.

- Research rank identifies the most important story, theme, or catalyst.
- Execution rank identifies the stock that can realistically be bought near the late session with a favorable next-day buyer path.
- The seven ranked stocks are a decision list and review sample, not seven buy orders.
- Rank 1-2 must pass a higher bar because they are the default execution names. Rank 6-7 must also pass a real execution bar because the user may buy them. If any execution candidate is too crowded, too high, unbuyable, or likely to cash out, it must be downgraded even when its story is attractive.

For overnight trades, never promote a candidate only because it is red-hot today. First decide whether today's strength creates tomorrow's buyer demand or tomorrow's seller inventory.

Apply these professional gates:

1. Market regime first: risk-on repair, risk-off defense, rotation, retreat/fade, or consensus cash-out. The likely next-day money path determines which themes can be rank 1-2.
2. Priced-in check: if today's close already reflects most of the catalyst, the stock needs exceptional late-session acceptance or a fresh after-hours catalyst to remain executable.
3. Crowding check: high-position, high-turnover, late-session抢筹, or full-consensus themes are downgraded unless they show healthy divergence and clear next-day incremental buyers.
4. Buyability check: sealed limit-up, one-word board, or impossible entry is a sector flag, not an execution candidate.
5. Buyer-source check: each execution candidate must identify who may buy tomorrow: fresh-news buyers, front-row substitution demand, capacity-core allocators, weak-to-strong repair traders, or risk-regime rotation funds.
6. Gap/rush/continuation distinction: label whether the trade seeks a gap-open premium, opening-rush premium, low-open repair, intraday continuation, or is mainly a consensus-profit-taking risk. The next-day sell plan must match the label.

## Next-Day Cash-Out Avoidance

The strategy must actively avoid stocks that are likely to become next-day cash-out inventory. Do not treat "today red" or "today strong" as a buyer story by itself.

Before finalizing rank 1-2, run a cash-out filter:

- If today's gain mainly came from old news, broad theme emotion, or late-session chasing without fresh after-hours continuation, downgrade.
- If many short-term participants are likely holding the same obvious profit and the next buyer source is unclear, downgrade.
- If the stock is high-position, high-turnover, late-pumped, or closes near the high after a crowded run, require stronger proof of healthy换手 and next-day incremental demand.
- If the stock is only a follower of a sealed leader, the follower must have its own acceptance and liquidity; name similarity is not enough.
- If a stock is green today but the theme is likely to rotate away tomorrow, treat it as potential seller inventory.

Conversely, give extra attention to under-recognized hard-catalyst stocks that lead a relevant board, show steady afternoon acceptance, and have a fresh price/commodity/order/policy catalyst. These can be better overnight setups than the most crowded hot names.

## Candidate Pool Ban

Do not use `rankings.overnight_candidates` or `rankings.active_candidates` for overnight recommendations.

These candidate pools are biased toward stocks that are strong or active today. For this user's overnight strategy, that bias is dangerous because today's active stocks often become tomorrow's seller inventory. The skill must ignore those lists when building, ranking, validating, or explaining the final seven stocks.

Forbidden uses:

- Do not open, read, quote, sort, filter, or compare `rankings.overnight_candidates`.
- Do not open, read, quote, sort, filter, or compare `rankings.active_candidates`.
- Do not use `market_score`, `high_open_score`, `next_day_accept_score`, `execution_grade`, or `rotation_risk` from those candidate pools.
- Do not say a stock is better or worse because it is inside or outside those candidate pools.

Allowed market facts from the snapshot:

- raw all-market stock quotes from `raw.stock_spot`;
- limit-up, previous-limit, strong, broken-limit, and DTGC pools as factual market-state evidence;
- `rankings.pool_industry_heat` only as a board-heat summary derived from pools, not as a candidate source;
- `rankings.top_amount` and other broad all-market summaries when they reflect market-wide liquidity, not a preselected overnight candidate list.

The final seven must come from analyst-first full-market reasoning: latest hard news -> industry-chain map -> all tradable A-share scan -> trend/hard-logic targets -> quiet ignition scan -> strongest-limit low-position scan -> late-session acceptance -> announcement risk.

## Full-Market + Bottleneck Research Gate

For overnight trades, `serenity-bottleneck` is used to improve hard-logic discovery, not to restrict the stock universe.

When nightly Serenity research files exist, read them as supplemental hard-logic context:

- `data_research/serenity/latest_watchlist.json`
- `data_research/serenity/latest_report.md`
- `data_research/serenity/rejected_candidates.md`

These files are not a candidate pool to rank mechanically. The overnight recommendation must still scan the full tradable A-share market, read today's news/announcement increment, read the latest valid market snapshot, and then merge Serenity hard-logic names with full-market capital-confirmed names.

For overnight trades, do not confuse "hard-logic downgrade" with "cannot rise". A-shares often reprice future expectations before orders, certifications, or earnings appear. Classify Serenity-related stocks as:

- `current_hard_logic`: direct current business/order/revenue/price evidence.
- `future_expectation`: validation, sample, capacity, customer, price-rise, or order expectation that funds are starting to price.
- `pure_concept`: only label similarity, or the company clearly denies the product/business/order.

`future_expectation` names can rank when the market is actively discovering them and tomorrow's buyer source is clear. They must be labeled as expectation trades, sized smaller, and checked for crowding/cash-out risk. Never describe them as already-verified hard chokepoint beneficiaries.

Use a two-engine workflow:

1. Full-market engine: scan all ordinary tradable A-shares from news, policy, announcements, sector strength, limit-up logic, amount leaders, quiet trend structures, and late-session acceptance.
2. Bottleneck engine: for supply-chain hard themes, apply the Serenity method to locate the scarce node and true beneficiaries. This is especially useful for AI hardware, PCB/CCL, glass substrate, MLCC, semiconductor materials, electronic specialty gases, optical communication materials, power equipment, resource price-rise chains, and other industrial bottlenecks.

Then merge the results:

- Stocks confirmed by bottleneck research become hard-logic candidates, especially pre-ignition trend names and quiet acceptance names.
- Stocks confirmed only by market action can still rank when they are true leaders/capacity cores and tomorrow's buyer source is clear.
- Stocks found by bottleneck research but not confirmed by market data stay watchlist unless late-session acceptance and next-day buyer logic appear.
- Stocks found by market action but failing bottleneck/business verification must be labeled emotion/front-row trades, not hard-logic trades.

Never replace one closed pool with another. The correct path is: full-market scan -> bottleneck/chokepoint research -> full-market market validation -> next-day buyer ranking.

## Hidden Trend Hard-Logic Targets

Some of the best overnight winners are not the hottest names at 14:45. They are trend stocks inside a hard catalyst chain that are still buyable before the market fully prices the next-day continuation. The skill must actively search for these targets.

This pattern is especially important when:

- the strongest direct beneficiaries are sealed limit-up or hard to buy;
- the catalyst is a price/supply-demand shock, such as electronic specialty gases, tungsten, molybdenum, rare metals, MLCC, PCB materials, optical communication materials, or other industrial materials;
- the theme has appeared in news for multiple days and is being confirmed by board leaders, not just one headline;
- the stock is a real industrial-chain beneficiary or equipment/material supplier, not a loose name association;
- the stock trends above key prices, shows 2-3 day accumulation, and has steady late-session acceptance rather than a final-minute spike;
- today's gain is moderate, but the theme leaders are locked and tomorrow's money may search for buyable extensions.

For these stocks, do not reject them only because the daily gain is not spectacular. They must be manually evaluated through: hard catalyst -> industry-chain relevance -> trend structure -> late-session acceptance -> next-day buyer source -> announcement risk.

Examples of logic to learn from: electronic specialty gas / WF6 price-rise chains, semiconductor material equipment chains, and other hard-price industrial chains where a trend stock can close only mildly strong today but become tomorrow's limit-up or major continuation target.

## Pre-Ignition Trend Logic Targets

The skill must also search for stocks before the obvious launch day. Some of the best overnight trades are not already limit-up or today's hottest names; they are hard-logic trend stocks that have been walking upward for several days and are waiting for a catalyst, board confirmation, or fund recognition to ignite.

This pattern includes stocks like Jin'an Guoji-style trend logic: a real industrial-chain beneficiary, steady upward trend, repeated acceptance on pullbacks, moderate volume expansion, and a hard theme such as PCB/CCL/electronic materials, semiconductor materials, price-rise chains, domestic substitution, AI hardware supply chain, or policy-backed advanced manufacturing.

Scan for these traits before ranking:

- 5/10/20-day trend alignment or repeated higher lows;
- price above key moving averages, with pullbacks not breaking trend support;
- 2-5 day accumulation with moderate gains, not one-day emotional spike;
- afternoon and late-session acceptance without obvious distribution;
- theme leaders or same-chain stocks already confirming, but this stock is still buyable;
- real product/order/price/capacity/profit relevance, not loose concept similarity;
- market has not fully priced the story, leaving next-day continuation room.

These stocks can be ranked even if today's gain is only modest. If the thesis is strong, label them as "盘中延续型" or "趋势启动前埋伏型" and explain what would make tomorrow's money discover them. Do not reject them for being less exciting than a limit-up stock.

## Quiet Acceptance / Next-Day Discovery Pattern

The skill must actively look for quiet hard-logic stocks that look ordinary today but may become tomorrow's discovered target. This is different from chasing today's hot leader. The ideal pattern is a real catalyst-chain stock with a calm tape, rising structure, and late-session acceptance while the market is still focused on flashier names.

This pattern is especially important when the user wants an overnight trade with a better red-exit chance than a crowded hot stock. Search for it before final ranking, even if it does not appear in obvious active lists.

Preferred traits:

- Daily gain is modest or controlled, often 0%-4.5%, but not weak relative to its theme.
- The stock has a 3-5 day rising structure, higher lows, or repeated pullback acceptance above key moving averages.
- Intraday action is not a final-minute vertical spike. Price should hold above the intraday average/VWAP or reclaim it before the late-session plan.
- Volume expands moderately versus recent days, not exhaustion-style volume after a blow-off move.
- The theme's direct leaders or capacity cores already confirm the chain, but this stock is still buyable and not fully priced.
- The stock has a real company/industry link to a hard catalyst: order, price rise, supply shortage, policy landing, capacity expansion, domestic substitution, AI hardware, semiconductor equipment/materials, PCB/CCL, optical communication, advanced packaging, power equipment, or other current hard line.
- Late-session acceptance is steady: near the day's upper area, no obvious 14:30-14:55 distribution, and no sudden fake pull with immediate fade.
- Announcement risk is clean, especially no fresh abnormal-move warning, clarification, reduction plan, regulatory inquiry, or performance surprise.

For each candidate that fits this pattern, state what will make tomorrow's money discover it. Examples: front-row stocks are sealed and unavailable; fresh news lands late in the day; tonight's media/analyst discussion may map the hard chain; the sector needs a buyable low-/middle-position extension; or the stock's company-level catalyst is under-recognized.

Do not over-promote quiet stocks with no catalyst. A calm chart without hard logic is only a technical guess. Quiet acceptance becomes rank 1-2 material only when hard logic, theme confirmation, and next-day buyer source are all present.

## High-Position Distribution Trap Filter

Quiet ignition is not the same as "not up much today". A stock can be red, flat, or only slightly green today and still be a high-position distribution trap if recent profit inventory is too heavy.

Before ranking any stock as rank 6, rank 7, or an execution priority, inspect the recent 10-15 trading days when local data exists:

- If the stock has already risen roughly 25%-30% or more from a recent swing low, it is not a low-position setup by default.
- If it has 2-4 consecutive high-turnover sessions, blow-off volume, post-limit-up failure, long upper shadows, or repeated intraday highs that are sold down, assume profit inventory is heavy.
- If today's "small gain" follows a large recent run and huge turnover, treat it as possible rebound/self-rescue rather than quiet accumulation.
- If the current session opens near the high, loses VWAP, cannot reclaim the prior close, or shows large sell volume into every repair, cancel quiet-ignition status.
- If the hard catalyst is real but same-chain leaders are not confirming, do not use the headline to override weak tape.

Hard rule: rank 6 must show real stabilization, not just a lower same-day gain. Real stabilization means higher lows or a rebuilt base, controlled volume, VWAP/late-session acceptance, and a clear next-day buyer source. If recent data shows high-position heavy selling pressure, label the stock "兑现风险型/观察" or remove it, even when the industry news is hard.

## Seven-Candidate Structure

The overnight output must contain exactly seven candidates, and ranks 6-7 are real execution candidates when they pass their gates, not casual bonus ideas.

Use this structure:

1. Rank 1: best red-exit probability and strongest executable overnight setup.
2. Rank 2: second executable setup or replacement for rank 1.
3. Rank 3: main-theme capacity/core stock with a clear next-day buyer path.
4. Rank 4: low-/middle-position hard-logic trend stock that has not fully priced the story.
5. Rank 5: higher-elasticity candidate, only when its risk is controlled.
6. Rank 6: quiet ignition candidate. This is a stock that has stabilized or is only slightly red/green, has a fresh or continuing hard catalyst, and may be discovered tomorrow.
7. Rank 7: low-position acceptance candidate from the day's strongest limit-up logic. This is the buyable same-chain extension when the strongest limit-up stocks are sealed, crowded, or difficult to enter.

Ranks 1-5 optimize for next-day red/positive exit probability. Rank 6 optimizes for quiet ignition: stable tape plus a catalyst that may make tomorrow's funds reprice it. Rank 7 optimizes for relay diffusion: the day's strongest sealed/limit-up logic may push funds into a lower-position, better buyable stock tomorrow.

The final recommendation must include a two-stock and, when justified, a three-stock execution combination. If the market is weak or the evidence is not hard enough, say clearly that only one or two should be bought. Do not recommend three just because seven names are listed.

## Quiet Ignition Candidate Gate

Rank 6 must be selected with a "big-stock intuition plus data" mindset: a stock that looks calm today but has the ingredients for tomorrow's sudden repricing.

Required traits for rank 6:

- The stock has stabilized after a pullback, or has been walking up for several days with higher lows.
- Today's gain is usually small or controlled, often -1% to +3.5%; up to about +5% is acceptable only when the theme is strong and the stock is not crowded.
- It is not merely flat. It must show late-session acceptance: reclaiming/holding VWAP or average price, closing in the upper half of the day, or absorbing sell pressure without breaking structure.
- It has a hard catalyst: fresh news, policy, order, price rise, supply-demand change, capacity/project progress, industry event, or a company-level announcement.
- The theme or same-chain leaders are already confirmed by market data, so tomorrow's funds have a reason to discover the stock.
- It has clean announcement risk.
- It must pass the high-position distribution trap filter: no recent blow-off run with repeated huge turnover, no post-limit-up failure, no heavy profit inventory that is likely to sell into tomorrow's repair.

Rank 6 can be a real buy. Provide an entry area, abandon condition, suggested position, and next-day sell plan. If it lacks market confirmation, keep it as "观察/小仓试错" and do not put it into the three-stock execution combination.

## Strongest-Limit Logic Low-Position Candidate

Rank 7 must start from the day's strongest limit-up logic, not from a random low-position stock. First identify the strongest sealed/limit-up or high-recognition logic of the day, then find the buyable same-chain stock with the best late-session acceptance and next-day relay path.

Required traits for rank 7:

- The anchor logic is one of the strongest of the day by board breadth, limit-up quality, capacity participation, news hardness, and fund flow.
- The direct leaders are sealed, too crowded, too high, or poor risk-reward for late-session buying.
- The candidate is genuinely related to the same industry chain, not just name/theme similarity.
- It is lower-position or less crowded than the leaders, but still shows recognition through volume, relative strength, or late-session acceptance.
- Tomorrow's buyer source is clear: front-row substitution demand, same-chain diffusion, low-position补涨, or capacity funds seeking a buyable extension.
- It must not be a weak follower that rises only because the whole board is green.

Rank 7 can also be bought when it is stronger than ranks 3-5 on execution quality. If the anchor logic is already climaxing and likely to cash out tomorrow, rank 7 must be downgraded or labeled observation only.

## Required Workflow

0. Confirm the trading calendar before collecting candidates.
   - Record the current date/time, latest completed A-share trading date, exact next A-share trading date, closed dates in between, and total calendar nights carried.
   - Label the setup as normal overnight or cross-weekend/cross-holiday inventory.
   - If the calendar is not confirmed by a reliable source, stop the executable workflow and output research-only observations.

1. Update or read news first.
   - From the project root, run current news collection when network is available:
     `venv/bin/python main.py --source cls eastmoney_global cninfo ndrc --days 1 --log-level INFO`
   - Then summarize local data:
     `venv/bin/python skills/overnight_stock_picker/scripts/news_snapshot.py --data-dir data_dev --days 7 --limit 80`
   - Read Serenity research cache when available:
     `data_research/serenity/latest_watchlist.json`, `data_research/serenity/latest_report.md`, and `data_research/serenity/rejected_candidates.md`.
   - Use the Serenity cache only as hard-logic background. Check its timestamp/news window and rejected reasons. If it is stale or missing, say so and continue with full-market analysis.
   - Then generate a market snapshot when AkShare is available:
     `venv/bin/python market_data/market_snapshot.py --mode overnight`
   - Read the latest valid market snapshot from `data_market/latest_overnight_snapshot.json`. If `data_market/latest_custom_snapshot.json` is newer, valid, and more relevant to the current late-session decision, use it instead and clearly label the data scope.
   - Do not use failed or zero-stock snapshots as current market truth. If the latest file has `stock_count=0`, fall back to the newest valid snapshot and state the timestamp.
   - Also inspect recent local market history before final ranking: prior `data_market/YYYY-MM-DD/overnight_snapshot.json`, `custom_snapshot.json`, `morning_snapshot.json`, plus `data_market/research/` files when they help identify trend alignment, pool tags, repeated acceptance, or historical high-open/overnight behavior.
   - Multi-day comparison is required whenever those files exist. Use at least the latest 3 trading days and preferably 5-7 trading days to judge theme persistence, breadth trend, limit-up quality, candidate accumulation, and whether today's action is early confirmation or late cash-out.
   - When the current snapshot has missing board or fund-flow endpoints, keep the valid stock quotes but backfill theme/fund context from the most recent complete local snapshot and state the limitation.
   - Do not let data collection perfection block the trade. If the user asks around 14:30 and data is still being refreshed, use the latest valid data and deliver the plan by the execution window, then optionally provide a quick cancellation update if a later snapshot invalidates it.
   - If crawling fails, still read the latest saved `data_dev` files and clearly state the newest timestamp used.

2. Determine the market style.
   - Check major indices, industry/concept board leaders, market breadth, turnover, limit-up count, broken-limit ratio, strong-pool composition, and whether funds are attacking growth, policy themes, defensive sectors, or small-cap emotion.
   - Compare today's market style with recent local snapshots across multiple trading days: whether breadth is improving or weakening, whether the main line is continuing or rotating, whether limit-up quality is rising or falling, and whether candidate themes have been accumulating for multiple days.
   - Do not classify a theme as early/confirmed/climax/fading from today's snapshot alone. Use the multi-day evidence unless older data is unavailable.
   - Identify the strongest 1-2 tradable themes for tomorrow's upside premium.
   - Build the next-day capital-path map before selecting rank 1-2: risk-on repair, risk-off defense, same-theme continuation, consensus cash-out, or rotation into fresh news. Then choose stocks that actually belong to that path.
   - Treat broad-market strength as a regime input, not a stock-selection answer. A strong next morning can still punish defensive inventory, high-turnover emotion, and yesterday's crowded themes if money rotates elsewhere.
   - News and policy are catalysts; real money flow and price strength decide the final pick.
   - Classify each major theme as one of: not started, early start, confirmed, climax, or fading. Overnight priority is: early start, then confirmed themes with healthy divergence support, then buyable front-row/core stocks before climax. Purely unstarted themes go to watchlist unless the market has begun to confirm them; climax or fading themes must be downgraded unless there is exceptional late-session support.
   - Before scoring candidates, answer the "overnight three questions": whether the main theme has a next-day relay reason, whether the stock has real divergence support, and whether tomorrow is likely to become consensus profit-taking.
   - Use `data_market` to confirm all-market行情, board strength, fund flow, limit-up/broken-limit pools, and whether late-session candidates are market-confirmed rather than only news-driven.
   - Today's strong theme is only a candidate source, not a buy reason. Before recommending it, judge whether tomorrow is more likely to be continuation, healthy divergence, consensus profit-taking, direct fade, or rotation into a new theme.
   - If the strongest current theme is likely to cash out tomorrow, do not rank its high-position or high-turnover stocks in the top two unless they have fresh hard news or exceptional 14:30-14:45 acceptance; use the final 10 minutes only as a cancellation/risk check.
   - In a weak market, automatically lower position size and require a harder next-day buyer story. Do not recommend two same-theme weak-confirmation trades.

3. Build candidates only from the strongest themes.
   - Prefer front-row stocks, high-recognition stocks, sector leaders, comeback leaders, or capacity leaders with visible capital inflow.
   - Do not mechanically map every news item to stocks. Use news to build theme hypotheses, expand only high-impact and market-confirmed themes into full-market stock maps, and let current market data decide which stocks are leaders, cores, low-position catch-ups, or weak followers.
   - For supply-chain hard themes, run a Serenity-style bottleneck pass before final ranking: identify the scarce industrial node, direct beneficiaries, capacity cores, and buyable substitutes. Treat the result as a hard-logic research list, not as the final universe.
   - Merge the Serenity hard-logic layer with the full-market capital-confirmation layer. A Serenity name without late-session acceptance stays watchlist; a non-Serenity name with strong next-day buyer logic can still rank.
   - Keep future-expectation names eligible when they have a clear next-day buyer path: tonight's story will ferment, front-row names are sealed, same-chain leaders confirm, or the stock shows quiet acceptance before full market discovery.
   - Add a reverse-scan step: for each fresh hard-news theme, search the full stock universe and board leaders. A stock that leads a relevant board, has steady gains, and has a fresh hard catalyst can be promoted into the seven-candidate list after execution checks.
   - Add a hidden-trend scan: search all tradable stocks in the same hard catalyst chain for trend names that did not rank high but are quietly strengthening. Give special attention to buyable equipment/material suppliers when the direct front row is sealed. A stock with moderate gain today can be a better overnight candidate than a crowded high-score name if tomorrow's buyer source is clearer.
   - Add a pre-ignition trend scan: search all tradable stocks for hard-logic names with 5/10/20-day trend alignment, higher lows, steady volume, and sector/theme confirmation. The goal is to catch Jin'an Guoji-style trend stocks before they become obvious limit-up names.
   - Add a quiet-acceptance scan: search for ordinary-looking stocks in hard catalyst chains that are up modestly, holding trend/VWAP, showing steady 14:30-14:45 acceptance, and not yet fully crowded. These are potential next-day discovery targets and must be compared against today's obvious hot names.
   - Add the rank-6 quiet ignition scan after the main-theme scan and before final ranking. This scan must look for stabilized, low-visibility, hard-catalyst stocks that could be repriced tomorrow.
   - Add the rank-7 strongest-limit low-position scan after identifying the day's strongest sealed/limit-up logic. This scan must map the strongest logic into buyable low-/middle-position same-chain candidates.
   - Do not use `rankings.overnight_candidates` or `rankings.active_candidates` at all. The final seven must come from full-market reasoning: fresh hard news -> theme/industry chain -> all tradable stocks under the user's permission threshold -> current market validation -> execution/risk filters.
   - The tradable universe is ordinary A-share stocks the user can realistically buy without a 500K RMB permission threshold. Prefer main-board stocks; exclude STAR Market `688/689`, Beijing Stock Exchange-style restricted tickers, and other 500K-threshold names unless the user explicitly says they can trade them. Keep the existing default caution on `300/301` unless the user explicitly allows them.
   - Every candidate must have a concrete next-day buyer reason: continuing news/policy fermentation, market-recognized theme leadership, buyable substitute when the strongest board is unavailable, healthy divergence support, or late-session fund positioning.
   - Every execution candidate must identify a likely source of tomorrow's incremental money. If the answer is only "the sector was strong today", downgrade it to watchlist.
   - Use the late-session method as a filter, not as the only reason.
   - At 14:30 onward, prioritize stocks near the day high, above intraday VWAP/average price, with active turnover and no obvious late-session distribution.
   - Segment the late-session check around execution reality: the user's question starts the analysis, 14:45-14:50 is normally enough to produce the actionable plan, 14:52 is the preferred latest delivery time, and 14:55 is only a final cancellation/sanity check for sudden dives, VWAP loss, or fake pull-ups.
   - Do not recommend sealed limit-up stocks that the user cannot realistically buy.
   - Do not recommend stocks that require a 500K RMB trading-permission threshold, such as STAR Market `688/689` stocks or Beijing Stock Exchange-style restricted tickers. Prefer buyable main-board stocks unless the user explicitly says they can trade those markets.

4. Score candidates using the reference model.
   - Read `references/strategy.md` when detailed scoring or edge cases are needed.
   - Do not outsource selection to any prebuilt candidate list. Build the list from the analyst-first full-market scan only.
   - Ignore candidate-pool scores such as `high_open_score`, `next_day_accept_score`, `market_score`, and `execution_grade`. If those fields exist, they belong to the banned candidate pools and must not influence the recommendation.
   - Execution gate: do not put any stock into the final two-/three-stock buy plan unless it passes next-day buyer logic, fresh-catalyst or under-priced theme logic, late-session acceptance,公告风险, and tradability.
   - Red-exit gate: do not put any stock into the final buy plan unless it has a realistic next-day red/positive exit path. If the likely next-day path is only "may rise later if lucky" but there is no probable open/rush/repair/continuation window, downgrade it.
   - Cash-out versus relay test: large gain is allowed only when tomorrow's relay demand is stronger than tomorrow's profit-taking supply. If the next buyer source is vague, downgrade no matter how strong today's close looks.
   - Quiet-discovery upgrade: a modest-gain hard-logic stock can outrank a hotter stock when it has cleaner announcement risk, a clearer next-day discovery path, and a better red-exit probability.
   - When high-open evidence is weak but the stock has strong opening-rush evidence, label it as "冲高试错" rather than "高开主推". Strong opening-rush evidence usually requires one or more: previous-limit or strong-pool recognition, same-theme sealed front row that is unavailable, 30B+ RMB amount or clear capacity status, 5%-15% turnover, and a non-climax theme.
   - Recommend seven candidates even when the market is weak, because the user uses the list for decision and review. However, execution candidates must be execution-quality or explicitly labeled trial/watch; never hide a weak setup behind relative ranking.
   - If no candidate passes the execution gate, still rank seven and name the best relative one or two as trial-only choices; state clearly that the setup lacks priority-grade next-day evidence and is not a normal overnight execution day.
   - Clearly mark the final execution priority: normally buy the best one or two; allow a three-stock combination only when the third stock is a high-quality rank 6 or rank 7 setup, or another candidate clearly has independent buyer logic and controlled risk. Ranks not selected for the combination are backup/watchlist/review candidates.

5. Output in Chinese, concise and decision-oriented.
   - Give exactly seven ranked candidate stocks.
   - Start with a mandatory calendar header: current date/time, latest completed trading date, exact next trading date, closed dates in between, total calendar nights carried, and normal-overnight versus cross-weekend/cross-holiday classification.
   - Then give the data scope: latest market snapshot timestamp, whether board/fund endpoints were complete, which local historical market data was used, and how many recent trading days were compared.
   - In cross-weekend/cross-holiday output, use the exact next trading date instead of "tomorrow" throughout the execution and sell plan.
   - Include: stock name/code, current price and change, theme, analyst score, execution quality label, recommendation rank, premium type, overnight three-question judgment, tomorrow incremental-money source, red-exit path, red-exit failure signal, announcement-risk check, late-session acceptance in the actual observed window, multi-day market/trend evidence, why someone may buy it from the user tomorrow, suggested position, late-session entry area, and next-day sell plan.
   - If the stock is a pre-ignition trend logic target, explicitly state the trend evidence, catalyst path, and what would invalidate the pre-launch thesis.
   - Explicitly label rank 6 as "企稳点火票" and rank 7 as "最强涨停逻辑低位承接票".
   - End with a two-stock execution choice and a three-stock execution choice. If the three-stock choice is not justified, say so and give only the one-/two-stock plan.

## Selection Bias

For this overnight strategy, prefer:

- Same-day strongest theme leaders over isolated individual stocks, but only when tomorrow still has a buyer story.
- Stocks with fresh policy/news catalysts plus visible capital inflow, especially when the expectation is not fully priced.
- Stocks that match the likely next-day capital path, not merely today's late-session winner.
- Early-start themes and confirmed themes with healthy divergence support over unconfirmed imagination or full-consensus climax.
- Pre-ignition hard-logic trend stocks with rising structure, real industry relevance, and theme confirmation, even when the same-day gain is only moderate.
- Stocks that are strong after 14:30, not only strong in the morning.
- Stocks with 50-500B RMB circulating market cap when possible; smaller is allowed only for clear emotion leaders, larger only for sector capacity leaders.
- Turnover around 5%-15%, volume ratio above 1, active money, and a healthy K-line. Turnover above 25% is usually a next-day low-open risk unless it is a clearly successful, market-recognized divergence.
- Capacity or recognition: 30B+ RMB daily amount, previous-limit/strong-pool overlap, or same-theme front row sealed and unavailable.

Avoid making a stock the top pick when:

- It does not have a clear next-day red/positive exit path for the user's one-night trade, even if the long story is attractive.
- It is already sealed at limit-up or effectively impossible to enter.
- It requires 500K RMB account permission, including STAR Market `688/689` stocks and Beijing Stock Exchange-style restricted tickers.
- It is only a weak follower while the sector leader is available.
- It has large net outflow, late-session diving, or repeated failed sealing.
- It is a pure social-media concept without real board strength.
- It has only a news story but no market confirmation, unless it is marked as a watchlist candidate with reduced confidence.
- It is today's hottest stock but tomorrow is likely to be pure consensus profit-taking.
- It is a defensive/cyclical pick while the likely next-day regime is risk-on repair, unless it has its own hard catalyst and clear buyer source.
- It is a high-beta technology/emotion pick while the likely next-day regime is risk-off defense, unless it has fresh hard news and exceptional late-session acceptance.
- It is too perfectly抢尾盘: close position near the absolute high after a crowded run without fresh catalyst; recent samples show this can be a consensus-profit-taking risk.
- Turnover is above 25% with no clear successful divergence story.
- It is up 7.5%-9.3% and tagged as a hot short-term name, unless the plan explicitly treats it as likely low-open then repair/rush, not direct high-open.
- It is in today's strongest board but has no fresh overnight catalyst or no next-day incremental-money source.
- It is only an upward chart without a hard industrial/news logic or without same-chain market confirmation.
- The user already holds too much of the same weak theme and the pick would increase concentration risk.

## Seven-Candidate Execution Rule

The seven ranks are not seven buy orders.

- Rank 1: default execution candidate if it meets the late-session trigger.
- Rank 2: execute if it is independent enough from rank 1, has a clear red-exit path, or rank 1 becomes too high/too weak.
- Ranks 3-5: main-pool backup/watchlist/review candidates; buy only if they show clearly better late-session confirmation than the selected names.
- Rank 6: quiet ignition candidate; can be the third buy when the stabilization, catalyst, theme confirmation, and red-exit path are all clear.
- Rank 7: strongest-limit low-position acceptance candidate; can be the third buy when the anchor logic is strong and the candidate is the best buyable same-chain extension.
- Because the user may execute rank 1-2 and may also buy rank 6-7, never use ranks 1-2, 6, or 7 as filler. If the market has no priority-grade setup or no credible red-exit path, label the relevant ranks as "试错级/观察级", not execution-grade.
- If all seven have low confidence, still rank them but recommend trial-level position only.

When giving the final buy plan, provide:

- Conservative plan: normally 1-2 stocks.
- Aggressive plan: up to 3 stocks only if the third has independent logic and controlled risk.
- Weak-market plan: one stock or no heavy position.

## Next-Day Sell Discipline

The user intends to sell no later than the next trading day. Always provide an exit plan:

- Gap-open premium: if high open cannot continue upward in 5-10 minutes, sell.
- Opening-rush premium: if flat/small-low open repairs and rushes, sell the first strong rush unless the sector and stock both confirm trend continuation.
- Low-open repair: if it cannot turn red or reclaim key price within 10-15 minutes, sell.
- Intraday-continuation premium: holding past the morning is allowed only if the stock stays above VWAP/key support, the theme remains in the top market path, and volume confirms continuation rather than distribution.
- Afternoon continuation: if the morning trend is strong, use late-morning or afternoon acceleration as the sell window; do not carry beyond the next trading day for this strategy.
- Rushes near limit-up but cannot seal: sell at least half, often all for this strategy.
- Strong one-word limit-up or fast sealed board: hold only while sealed; open and fail to reseal means sell.

Never promise a stock will rise. Use probability language such as "相对最优", "明天溢价概率更高", and "需要按次日纪律卖".
