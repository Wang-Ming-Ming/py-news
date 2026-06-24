---
name: morning_stock_picker
description: 'Use this skill when the user asks for a pre-market or opening-session A-share stock-picking plan, usually around 8:40-9:30 China time: recommend eight ranked stocks, including a dedicated low-position pin-reversal/MACD-turn candidate, report relevant overseas-sector conditions for recommendations and confirmed holdings, and give time-bound holding sell discipline using py-study news, market data, auction/opening data, and top short-term trader risk control.'
---

# Morning Stock Picker

This skill builds a morning A-share trading plan. Identify five main stocks, then add rank 6 quiet ignition, rank 7 strongest-limit low-position acceptance, and rank 8 low-position pin-reversal/MACD-turn. Give concrete execution conditions for all eight.

The recommendation is a trading plan, not a promise. Use probability language such as "相对最优", "更容易被资金攻击", "竞价确认后再执行", and "不满足条件就放弃".

## Objective Server Data Boundary

The server is a data source only. It has no AI and must not provide main-line judgments, catalyst grades, announcement-risk conclusions, candidate pools, scores, or recommendations. Codex performs every analytical judgment locally.

At the start of a live request, run:

`venv/bin/python skills/morning_stock_picker/scripts/server_context.py`

This sync is mandatory and must be the first data action even when a local cache already exists. Connection settings resolve from process `STOCK_DATA_SERVER`/`STOCK_DATA_TOKEN`, then the repository-root `.env`, then the legacy `~/.config/stock-data-client/config.json`. All three stock skills share the single `data_server_cache` directory and `data_server_cache/latest_context.json`; never create a skill-specific objective-data cache. Verify calendar/data health/snapshot time, expected counts, `sync_duration_seconds`, `using_cached_data`, and that the context `mode` matches this run, then use the referenced gzip feature file, pools file, news index, and announcement index. Fetch full news/announcement text by ID only when needed. Do not load the full-market raw file into conversation context; use local client query commands to narrow objective rows before reasoning.

If sync fails, use the newest complete local cache only when its timestamp is relevant and state the fallback clearly. Server fields are facts, not conclusions; infer themes, catalyst relevance, risk, and final ranking yourself.

## Confirmed Holdings Ledger

Use `data_portfolio/current_holdings.json` as the only persistent source of current holdings. Do not reconstruct holdings from old screenshots, chat history, recommendation records, or personal preference.

- When the user explicitly confirms a buy/add, update the ledger with `venv/bin/python analysis/holding_ledger.py buy --code CODE --name NAME --quantity QTY --price PRICE`.
- When the user provides a current-position snapshot or correction, use `upsert` with the confirmed fields.
- When the user explicitly confirms a partial sale, use `sell --code CODE --quantity QTY`; when fully sold, use `sell --code CODE` so the stock is removed.
- If quantity or cost is unknown, preserve the confirmed stock with `upsert` and leave unknown fields null. Never invent missing trades.
- Read the ledger on every morning run. Keep new-stock selection independent from holdings, then use holdings only for exposure, concentration, and sell-risk management.

## Highest Priority Rule

For live trading analysis, use the latest valid data available while the analysis is being performed, as long as it is relevant to the decision. Do not ignore newly available auction, opening, market, or news data merely because it appeared after the first user message in the same live request.

- If the user asks in a live morning session before 9:15, use the latest news, policy,公告, overnight market, and prior-day market data available at analysis time. There is normally no auction data yet.
- If auction data becomes available during analysis, it may be used and should be clearly labeled.
- If opening data becomes available during analysis, it may be used and should be clearly labeled.
- Only enforce a hard historical cutoff when the user explicitly says the scenario is a replay,假设, backtest, or "只使用某时间之前的数据".
- Never use future or unavailable data in a historical replay.

Do not infer sector leaders from the user's holdings, repeated conversation history, or the user's stated preference. Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current market data: limit-up height, sealing strength, turnover, sector leadership, capital flow, 2-3 day persistence, and policy/news mapping.

The user may expect to buy one or two stocks from the morning plan. Still, do not loosen execution standards: rank eight relative candidates, identify the best one or two, and mark ranks 6-8 as real special candidates only when they pass their gates. Label them watch/trial when news strength, market confirmation, auction/opening confirmation, or risk-reward is insufficient. Never turn a weak setup into a high-confidence recommendation just because the user plans to trade.

## Relevant Overseas-Sector Check

Before the market judgment, batch-check only the overseas markets directly relevant to (a) the final eight recommended themes and (b) current holdings in the ledger. Do not produce a broad global-market encyclopedia.

For each relevant theme, report the newest available benchmark and timestamp: related US/HK-listed sector or representative assets, key commodity/futures/FX/rates where directly relevant, and the overnight move. Distinguish `利多 / 中性 / 利空 / 无可靠直接映射`; never convert correlation into a proven causal relationship. If no reliable direct benchmark exists, say so instead of forcing a mapping.

Use overseas data as both an opportunity filter and a holding-risk veto:

- Negative overseas mapping plus weak A-share auction/opening confirmation lowers candidate rank and position.
- A holding whose related overseas benchmark is sharply weak must receive an explicit early sell/reduce plan; do not default to waiting until the close.
- Positive overseas mapping does not override an A-share stock that gaps and loses VWAP, opens as the high, or shows sector-wide cash-out.
- Include source time and freshness. Stale overseas data cannot justify an executable decision.

## Message-First Morning Logic

Morning stock picking must be message-first, not yesterday-strength-first. Start from today's newest available catalysts, then identify affected themes, directly named companies, and market-recognized tradable stocks.

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
2. Search the full A-share market for directly named companies, verified business beneficiaries, and stocks already recognized by current market data.
3. Use prior-day market data only to validate whether funds already have a base:辨识度,成交额,涨停/炸板, sector breadth, capital flow, and兑现 pressure.
4. Use auction/opening data as final confirmation when available.
5. Output exactly eight candidates: five main candidates plus ranks 6-8 special candidates, then identify only the best 1-2 as execution priorities.

If today's fresh message conflicts with yesterday's strong sector, respect today's new message first. Yesterday's strength becomes a risk check only. Unless 9:15 auction or 9:30 opening data clearly confirms yesterday's main line is still strengthening, do not force recommendations into yesterday's strong direction.

## Analyst-First Full-Market Scan

Do not let a system-generated candidate pool decide the recommendation list. Candidate pools, rankings, and scores are only secondary review tools after the analyst-first scan.

The real selection path is:

1. Identify the hardest fresh message themes: price increases, orders, policy landing, overseas mapping, supply-demand change, or direct company catalysts.
2. Search the full tradable market for directly named companies, verified beneficiaries, leaders, front-row names, low-position catch-ups, and under-recognized hard-catalyst stocks.
3. Verify company relevance only from public company facts, original announcements, or reliable source text. Do not build an expanded industry-relation model during recommendation runs.
4. Filter by the user's realistic tradability: ordinary A-share stocks that do not require a 500K RMB permission threshold. Prefer main-board stocks; exclude STAR Market `688/689`, Beijing Stock Exchange-style restricted names, and other 500K-threshold names unless the user explicitly allows them. Keep default caution on `300/301`.
5. Use market snapshots, rankings,涨停池,强势池,板块热度,成交额,资金流, and auction/opening data only to validate or reject the analyst list.

A stock absent from local candidate rankings can still enter the final eight if it has a hard fresh catalyst, verified relevance, market recognition, and a buyable execution setup. A stock inside the candidate rankings can be rejected if it is crowded, old-theme, over-priced, or lacks next-buyer logic.

## Direct-Evidence Boundary

Do not load optional industry-research resources or perform upstream/downstream or scarcity inference during a normal recommendation run. Those resources remain stored but are intentionally disabled here.

Use only direct and fast evidence:

- the company is named in an original announcement or reliable report;
- public company disclosures verify the relevant product, order, customer, capacity, price, or business;
- current market data confirms recognition, liquidity, relative strength, and tradability;
- expectation trades are labeled as expectations rather than proven earnings logic.

Reject loose concepts and company-denied stories. Do not spend recommendation time deriving upstream/downstream substitutes from an anchor stock.

## Hard Catalyst Execution Upgrade

The highest-quality morning setups usually come from fresh, under-priced hard catalysts plus fast capital confirmation. Treat the following as priority rules:

1. Fresh hard catalyst window comes first. Give extra priority to messages released after the prior trading day's close and before today's open, especially company公告, major orders, bid wins, performance changes, buybacks, policy landing details, or industry events that the market has not fully priced.
2. Grade catalyst hardness. Direct company-level hard catalyst > policy landing > industry event with clear beneficiaries > overseas/commodity/rate mapping > repeated old theme or media imagination.
3. Grade beneficiary evidence. Direct company filing with amount/counterparty/date > verified company business plus reliable industry news > market-recognized theme leader > low-position catch-up > loose follower.
4. In weak markets, raise the bar. If breadth is weak or risk appetite is poor, only the hardest 1-2 setups can be execution priorities. The other three candidates are watchlist only unless auction/opening data confirms them.
5. Capital confirmation decides execution. A hard catalyst can override a weak sector for candidate selection, but it still needs auction/opening or live market confirmation: strong amount, relative strength, main-fund recognition, theme support, or clear逆板块 strength.

Do not reject a direct company-level catalyst only because the broader sector is weak. However, if the stock cannot show relative strength or资金承接 after the open, downgrade it immediately.

Do not use raw factor/channel vote count as the final morning rank. Treat channels as evidence and vetoes; ranks 1-2 must pass both buyer/exit and drawdown/cash-out-risk gates. Keep material risk announcements active for 15 calendar days unless a newer original filing resolves them.

## Professional Execution Gate

Separate analyst-quality ideas from trader-quality entries. A stock can rank high in the research candidate pool because the news is hard, fresh, and direct, but it cannot become an execution priority until the price, tradability, and opening承接 still offer a favorable risk-reward.

Apply these gates before naming the final 1-2 execution priorities:

1. Market regime first. Classify the morning as risk-on, weak repair, rotation, risk-off, retreat/fade, or consensus cash-out before ranking execution names. Weak breadth, high broken-limit pressure, fast rotation, or negative overseas markets automatically lower position size and raise the execution bar.
2. Catalyst is not enough. Grade whether the catalyst is under-priced at the current opening level. If a stock gaps up enough to consume most of the news value, downgrade it from "buy trigger" to "priced-in/兑现 test" until it proves承接.
3. Candidate rank is not execution rank. Research rank answers "which story matters"; execution rank answers "which stock can be bought at a good price with confirmed demand". A rank-1 research catalyst can become only a sector flag if it opens too high, cannot be bought, or fails承接.
4. Unbuyable strength is a flag, not a trade. One-word limit-up, sealed limit-up, or instant boards should be used to confirm the theme and locate buyable alternatives; do not list them as final execution recommendations.
5. High open needs gap classification. Judge whether a gap is breakaway/continuation, common, or exhaustion. In a weak or cash-out market, a prior-day weak stock that gaps sharply on news and makes the open its high should be treated as an exhaustion/兑现 risk unless it reclaims VWAP and expands volume on a second push.
6. Always identify the next buyer. For each execution name, state who is likely to buy after the user: fresh-policy buyers, event-driven buyers, sector relay funds, capacity-core allocators, front-row substitution demand, or weak-to-strong traders. If the next buyer cannot be identified, downgrade.
7. Execution requires a two-step confirmation. A high open is only the market seeing the news; confirmation is opening hold, VWAP/average-price support, sector synchronization, and a second volume push. Without that, the setup is observation only.

## Morning Eight-Candidate Structure

The morning output must contain exactly eight unique ranked candidates. Ranks 1-5 are the main morning attack list. Ranks 6-8 are dedicated special candidates and must not be casual filler.

Use this structure:

1. Rank 1: strongest executable morning setup after message-first and trading gates.
2. Rank 2: second executable setup or replacement for rank 1.
3. Rank 3: main-theme capacity/core stock or strong front-row alternative.
4. Rank 4: hard-logic trend or low-/middle-position candidate that has not fully priced the story.
5. Rank 5: higher-elasticity candidate or backup theme, only when risk is controlled.
6. Rank 6: quiet ignition candidate. This is a stock that may look stable, flat, or only modestly strong before/at the open, but has direct catalyst evidence or clear market recognition and a realistic chance to be repriced after opening confirmation.
7. Rank 7: strongest-limit logic low-position acceptance candidate. Identify the strongest sealed/limit-up or high-recognition theme, then select a buyable low-/middle-position stock only when public facts verify the same theme and current market data confirms it.
8. Rank 8: low-position pin-reversal candidate. Prefer the previous completed trading day's pin/long-lower-shadow structure, allow at most the latest three completed sessions when the base remains intact, then require a bottom MACD turn, current auction/opening confirmation, and fresh message/theme support.

Ranks 6-8 may become execution candidates when stronger than ranks 3-5 on tradability, confirmation, and risk-reward. Keep all eight codes unique. If the best pin-reversal setup is already in ranks 1-7, move it to rank 8 and replace its former slot. If rank 8 lacks message, theme, risk, or opening confirmation, still show the relative-best scanned setup but label it observation-only and do not invent a buy trigger.

Do not promise a stock will涨停. For rank 7, write "具备冲板/涨停预期" only when the anchor theme is strong, the candidate's relevance is directly verified, the opening tape confirms, and the price has not already consumed the risk-reward.

## Quiet-Ignition Anti-Distribution Gate

Rank 6 "企稳点火票" and rank 7 "低位承接票" must first prove they are not high-position distribution/rebound traps. A hard catalyst plus a small prior-day gain is not enough.

Before labeling any stock as quiet ignition, check the last 10-15 trading days when local data exists:

- Short-term position: if the stock has already risen roughly 25%-30% or more from the recent swing low, it is not automatically low-position or stable.
- Volume pressure: if the last 2-4 sessions show repeated huge turnover, blow-off volume, or heavy distribution after a limit-up/large candle, treat modest red/green action as a possible rebound or self-rescue, not accumulation.
- Price structure: if the stock recently failed near a high, produced long upper shadows, opened near the session high, or could not make smooth new highs after a limit-up, downgrade.
- Opening behavior: if today's open becomes the intraday high, or the stock drops quickly below prior close/VWAP after a gap, cancel the setup immediately.
- Theme support: if the hard-news theme is not being confirmed by current leaders and breadth, do not promote the stock just because the news is real.

Hard rule: a high-position, high-turnover stock with heavy profit inventory cannot be called "企稳点火" unless it has clearly rebuilt a base through multiple controlled pullbacks, lower turnover, higher lows, and renewed market confirmation. Otherwise label it "兑现风险/观察", or remove it from the final eight.

## Rank 8 Low-Position Pin Reversal

After the server sync, run:

`venv/bin/python analysis/low_pin_reversal_scanner.py --mode morning --limit 30`

Read [the shared pin-reversal rules](../references/low_pin_reversal.md). Treat scanner output as discovery evidence only. Inspect `live_breakouts` first when opening data exists, then `confirmed` and `scouts`. Prefer the previous completed trading day and allow at most the latest three completed sessions when the pin base remains intact; use today's auction/opening only to confirm or veto it.

Require a genuine low/middle position, a swept recent low followed by a strong close recovery, healthy amount, and a bottom MACD `red_turn` or `red_expanding` state. `green_contracting` remains observation-only unless a recent qualified pin is followed by a current break above the pin high/MA5 with rapid histogram contraction and opening confirmation. Then verify current news, public company relevance, theme strength, risk announcements, next buyer, and opening tape. A technical pattern alone cannot become an execution priority.

## Pre-Auction Plan Mode

The user may ask before 9:15, when there is no auction data. In that case, output a pre-auction plan, not a final confirmed buy list.

- Clearly label the data scope as "竞价前，无竞价数据" or equivalent.
- Use latest news, policy,公告, overseas markets, commodities/FX/rates, and prior-day market data.
- Give eight ranked candidates and the best 1-2 provisional priorities, but each must have 9:15/9:25/9:30 confirmation triggers.
- Scores before auction should reflect pending confirmation. Do not write "已确认" or high-confidence execution language before auction data exists.
- If a candidate's logic is strong but depends on auction confirmation, mark it as "盘前第一预案 / 等竞价确认", not "直接买".
- If auction becomes available during analysis, update the plan and clearly say the auction data has been added.

Recommendations must come from the full market and current real data:

- Do not recommend based on the user's holdings.
- Do not recommend based on stocks repeatedly mentioned in historical chat.
- Do not cater to the user's subjective preference.
- Sector leaders, front-row stocks, capacity cores, and low-position catch-up stocks must be confirmed by current data, not assumed.

## Required Workflow

1. Sync and validate server data first, then read news.
   - Run `venv/bin/python skills/morning_stock_picker/scripts/server_context.py`.
   - Verify shared `latest_context.json`, health, calendar, snapshot time, expected counts, mode, and cache fallback status before analysis.
   - Use only the server-backed news/announcement indexes under `data_server_cache` and fetch relevant original text by ID. Do not run local news collectors or read `data_dev`.
   - Read the snapshot, feature, pool, and recent-history files referenced by `data_server_cache/latest_context.json`. Do not generate or read local `data_market` snapshots.
   - If server sync fails, use only the newest complete context already under `data_server_cache`, state its timestamp and age, and lower confidence when it is stale.
   - Filter out news that is later than the user's request time.
   - Classify each key catalyst as pre-move, same-session, after-close, or post-board. Fetch originals before grading hardness.
   - Track both `published_at` and `event_at` for scheduled catalysts and re-surface verified events near their occurrence date.
   - For leading candidates, perform a targeted source-gap check of issuer official news, investor interactions, and industry-event notices only when the server evidence is insufficient.
   - Read `data_portfolio/current_holdings.json`; report its `updated_at` and never add or remove a holding unless the user explicitly confirmed the trade.

2. Check relevant overseas sectors in one batch.
   - Build the minimal theme set from provisional recommendation themes plus confirmed holdings.
   - Fetch only directly relevant overseas benchmarks, commodities, futures, FX, or rates; record quote time and whether the market is closed, live, or indicative futures.
   - Produce one compact mapping per theme: benchmark move, impact grade, affected recommendations/holdings, and the A-share confirmation needed.
   - If a holding has adverse overseas mapping, prepare its first reduce/sell trigger before ranking new buys.

3. Build today's message-theme map.
   - Start with today's newest valid news, policy, company announcements, overseas markets, commodities, FX/rates, industry events, and company-level hard catalysts.
   - Group messages by theme and grade them by freshness, hardness, market scope, company specificity, and whether they can change expectations today.
   - Search the full market for directly named companies, verified business beneficiaries, and market-recognized leaders or low-position candidates.
   - Do not invoke a separate industry-research skill or derive upstream/downstream candidates. Verify relevance from public company facts and current market behavior.
   - If a stock is an expectation trade rather than current hard evidence, keep it eligible only when auction strength, theme breadth, and opening承接 show that funds are actively pricing it.
   - Do not start by asking which sector was strongest yesterday.

4. Determine the likely morning market style and validate with prior-day data.
   - Before 9:15: use prior-day close, prior-day涨停复盘, sector strength, overnight overseas markets, commodities, policy, company announcements, and morning news.
   - During auction: add auction涨幅, auction volume, one-word limit-up status, weak-to-strong behavior, and whether the strongest theme is being confirmed.
   - After 9:30: add open, early分时承接, sector breadth, active money, and whether the candidate is above its intraday average price.
   - Before selecting stocks, classify yesterday's strongest themes as continuation, healthy divergence, or fade/rotation risk. This is a validation step only, not the anchor.
   - If today's message flow points to a new theme while yesterday's strong theme lacks fresh catalysts, prefer the new message theme unless auction/opening confirms yesterday's line.
   - Use the server-downloaded feature and pool files to confirm all-market行情, industry/concept strength, fund flow, limit-up/broken-limit pools, and ranking warnings. Do not use rankings as the source of recommendations.

5. Build an analyst-first full-market list.
   - Start from the whole A-share market and all sectors, then filter by the user's tradability rules.
   - Do not start from the local candidate pool. Build the list from fresh hard messages, directly verified company relevance, and all buyable stocks under the user's permission threshold.
   - Combine two sources: (a) directly supported stocks from the strongest message themes; (b) market-confirmed leaders and low-position candidates from current real data.
   - Prefer stocks mapped from today's strongest message themes, with high recognition, company-level catalysts, prior-day money traces, or clear policy/news mapping.
   - If a hard-logic stock is not in the generated candidate pool, still evaluate it manually by theme strength, board position, trend, liquidity, and execution risk.
   - Recommend exactly eight ranked candidates: five main candidates plus rank 6 quiet ignition, rank 7 strongest-limit low-position acceptance, and rank 8 low-position pin reversal, but mark the best 1-2 as the only execution priorities.
   - If the strongest stock is sealed limit-up or not realistically buyable, use it only as a sector flag and recommend a buyable same-theme alternative.
   - A low-position observation stock cannot displace executable ranks 1-2 without auction/opening or hard-message confirmation.

6. Apply hard filters.
   - By default, do not recommend ChiNext/Growth Enterprise Market stocks such as `300/301` tickers, unless the user explicitly asks to include them.
   - Do not recommend stocks requiring a 500K RMB permission threshold, such as STAR Market `688/689` stocks or Beijing Stock Exchange-style restricted tickers, unless the user explicitly says they can trade them.
   - Avoid ST, delisting-risk, major negative公告, obvious fraud/regulatory-risk, or severe减持 pressure.
   - Avoid one-word sealed limit-up stocks as final buy recommendations because the user cannot realistically enter.
   - Avoid pure social-media concepts without news/policy/board strength support.
   - Avoid prior-day blow-off distribution, large bearish candle with heavy volume, or candidates with obvious sell-off risk unless the plan is explicitly a weak-to-strong reversal setup.
   - For rank 6 and rank 7, reject "fake quiet" structures: recent large run-up, consecutive huge turnover, post-limit-up failure, long upper shadows, or opening-as-high selling pressure. Do not let a fresh price-rise/news headline override visible high-position distribution.

7. Score candidates.
   - Read `references/strategy.md` when detailed scoring, auction logic, or output rules are needed.
   - Rank by message-first score and practical tradability, not by theoretical涨停 probability alone.
   - New message > old strength. Prior-day strength can lift confidence only after today's message and auction/opening logic are valid.
   - Run the low-pin scanner after sync, inspect the top objective rows, and independently verify the final rank 8 against messages, theme, risk, and current tape.
   - If no candidate reaches execution quality, still give eight ranked relative candidates, but state that the best 1-2 require small trial position, auction confirmation, or no trade if the trigger fails.
   - Do not rank by raw channel votes. Use independently supported evidence, explicit vetoes, and separate morning reliability records. Do not change factor weights from fewer than 40-60 forward decisions.

8. Evaluate confirmed holdings before new-stock execution.
   - For every ledger position, output `留 / 减 / 卖 / 禁止加仓`, relevant overseas-sector status, auction/opening confirmation, first action time, price/VWAP invalidation, and latest reevaluation time.
   - Never write only "继续拿着看看". A hold decision must state what evidence permits holding and what event forces a sale.
   - Use 9:35, 9:45, and 10:00 as decision checkpoints when live data exists. If adverse overseas mapping and weak A-share confirmation coexist, reduce at the first failed repair instead of waiting until the afternoon.
   - If the request arrives after a checkpoint, do not issue retrospective instructions. Use current live data, define the first action within the next five minutes, and force a new decision no later than ten minutes afterward.
   - Separate sunk cost from the decision. Cost price may define account loss, but it must not justify holding a broken setup.

9. Output in Chinese, concise and decision-oriented.
   - Include the data scope: live latest data or the explicit historical cutoff used.
   - Output a compact `相关外围板块行情` table covering only recommendation and holding themes, with benchmark, move, timestamp, impact, and affected stocks.
   - If the holdings ledger is non-empty, output `持仓早盘处置` before the eight recommendations. If empty, state that no confirmed holding is recorded.
   - Include today's main message themes and the direct evidence connecting each candidate to them.
   - Include the continuation/divergence/fade judgment for yesterday's strongest themes.
   - Give exactly eight ranked stocks.
   - For each stock include: stock name/code, reference price/current available price, theme, score, reason, auction/opening condition, buy trigger, abandon condition, and position size.
   - Explicitly label rank 6 as "企稳点火票" and rank 7 as "最强涨停逻辑低位承接票".
   - Explicitly label rank 8 as "低位插针反转票" and include pattern date, confirmation date/days since pin, low/recovery, range position, shadow/close position, pattern/current amount, MACD state, message/theme confirmation, next buyer, trigger, invalidation, position, and exit discipline.
   - End with the final execution priority: "只重点买第几名/哪两只", plus the key no-buy conditions. If rank 6 or rank 7 is better than ranks 3-5, explain why it can enter the execution pair.

## Mandatory Recommendation Journal

Before sending the final answer, seal the final eight-stock plan in `data_recommendations/daily_recommendations.json` with:

`venv/bin/python analysis/recommendation_journal.py record --mode morning --trade-date YYYY-MM-DD --input /tmp/morning_recommendation.json`

The input must contain `decision_time`, `market_judgment`, `data_context`, `overseas_sector_context`, `holding_actions`, exactly eight `candidates`, `focus_codes`, `no_trade`, and `response_summary`. `holding_actions` may be empty only when the confirmed holdings ledger is empty. Each candidate must include rank/code/name plus the actual thesis, catalyst/time class, reference price, auction/opening confirmation, buy trigger, abandon condition, position, risk flags, and sell discipline used in the answer. Rank 8 must also preserve its objective pin/MACD evidence and confirmation grade.

Do not edit or delete a sealed run after outcomes are known. A revised recommendation creates a new run; the journal preserves the earlier version and marks it superseded. If journaling fails, state that failure in the final answer instead of pretending it was recorded.

## Morning Execution Logic

Do not only chase high opens.

- 高开 0%-3%: usually the most comfortable range for fresh hard catalysts, but still requires auction/opening volume and sector confirmation.
- 高开 3%-5%: acceptable only after回踩不破均价/VWAP or second volume push confirms承接.
- 高开 5%-7%: default "priced-in/兑现 test" zone in weak, rotating, or risk-off markets. Do not chase the open; wait for a clear second confirmation.
- 高开 7%-9%: high兑现 risk; do not chase unless sector is extremely strong and the stock quickly seals or holds承接.
- 一字涨停 or sealed limit-up: sector flag only; not a final buy recommendation.
- 平开/小高开 0%-2%: acceptable when news is hard and the stock quickly放量上攻.
- 小低开 -1% to -3%: not automatically bad; buy only if it quickly turns red-to-green with sector confirmation.
- 大低开 below -4%: default abandon unless there is a very strong catalyst and fast repair.

## Position Discipline

- Morning plans should not imply full position.
- Normally recommend 1-2 execution stocks from the eight, with small-to-medium position per stock.
- If market style is weak or candidates are mainly high-open兑现 setups, lower position size.
- If the user already holds related stocks, mention concentration risk and avoid adding too much of the same weak theme.

## Sell Discipline

For short-term morning trades, always include an exit mindset:

- High open then cannot continue upward in 5-10 minutes: reduce or sell.
- Opens strong but breaks intraday average price with volume: reduce or sell.
- Weak-to-strong setup fails to turn red within 10-15 minutes: abandon or cut.
- Rushes near limit-up but cannot seal: take profit on at least part of the position.
- Strong sealed board: hold only while封单 stable; open and fail to reseal means sell.
- For every confirmed holding, define a first-action checkpoint and a latest reevaluation checkpoint; do not let "等反弹" silently become holding until the close.
- Adverse overseas-sector move plus weak auction/opening, failure to reclaim prior close/VWAP by 9:45, or sector leaders breaking down requires reduction or exit according to the stated plan.
- When a holding is sold and the user confirms the trade, remove it from `data_portfolio/current_holdings.json` immediately.
