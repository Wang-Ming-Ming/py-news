---
name: overnight_stock_picker
description: 'Use for late-session A-share selection and overnight plans. Independently scan the full ordinary main-board market, output five main candidates plus three dedicated special-logic candidates, verify real late-session acceptance, and give a strict next-trading-day exit plan.'
---

# Overnight Stock Picker

从全市场寻找尾盘可买、下一交易日具有接力或兑现窗口的普通主板股票。固定输出八只：前五只主候选，第六企稳点火、第七最强涨停逻辑低位承接、第八低位插针反转。

重大消息优先，但主题多事件共振、产业链硬映射、健康强趋势和启动前预期差同样可以排第一。市场弱时降仓，不用空推荐回避风险。

## Data and Calendar Gate

Run first:

`python skills/overnight_stock_picker/scripts/server_context.py`

Run this synchronization only once per recommendation. It must be incremental: download only missing/new server data and reuse the shared dated cache. Do not start a second synchronization merely to wait for a newer snapshot. If the single sync fails or stalls, use the newest complete local server-backed cache with an explicit timestamp/limitation; never let retries consume the trading window.

All stock skills share `data_server_cache/` and `latest_context.json`. Verify:

- context mode, server time, calendar, latest valid snapshot time;
- expected/actual counts, completeness, `using_cached_data`, and sync error;
- at least 3 and preferably 5-15 recent trading-day archives;
- availability of actual 14:30-15:00 snapshots versus historical-close-only data.

Use only server-backed objective data. Fetch relevant news/announcement originals by ID. The server never decides themes, hard logic, lifecycle, risks, candidates, or rankings; Codex does.

读取并遵守 [主题、产业链与趋势共振选股](../references/theme_chain_selection.md)。一级直接核心和二级硬映射均可推荐；二级公司若正处于扩产、洁净室、设备、材料、IC载板等当期资本开支兑现环节，可以排名高于一级公司。三级概念只能观察。

Prefer compact structured queries over printing or rereading multi-megabyte raw JSON. Read only the fields and originals needed for the current decision. Run independent local reads/checks concurrently when possible, but keep final judgment with Codex.

Confirm the exact next A-share trading day. If carrying across a weekend/holiday, state the extra nights, reduce position/confidence, and require a catalyst/buyer story capable of surviving the closure. Without a reliable calendar, output research-only observations, not executable prices or normal position sizes.

## Information-Time Gate

Use only information public by the actual decision time. Label catalysts as `pre_move`, `same_session`, `after_close`, or `post_board` from their published timestamps.

- Do not use an after-close announcement to explain or predict that day's first board.
- A keyword/title is discovery only. Read the original before calling it hard catalyst.
- Keep material risk announcements sticky for 15 calendar days unless an original filing resolves them.
- Track both publication time and event time. Re-surface verified scheduled events at T-3/T-1/T0.
- For top candidates, check issuer official news, investor interactions, and industry-event notices only when the server feed may have a material coverage gap. Preserve source/timestamp and never elevate a rumor.
- In a historical replay, enforce the requested cutoff and never use future market/news data.

## Decision Objective

For each top execution candidate answer:

1. Who is likely to buy it on the next trading day?
2. Why should relay demand exceed profit-taking supply?
3. Which exit path is most plausible: high open, opening rush, low-open repair, or intraday continuation?
4. What observable signal invalidates that exit path?

Rank 1-2 priority:

1. Positive/red exit-window probability.
2. Next-buyer clarity.
3. Catalyst freshness/hardness and beneficiary uniqueness.
4. Late-session acceptance and tradability.
5. Multi-day crowding, distribution, and announcement risk.

Do not convert raw factor/channel votes into final rank. Treat channels as independent evidence and vetoes. Require ranks 1-2 to pass both buyer/red-exit and drawdown/cash-out-risk gates. Morning and overnight channel reliability must be tracked separately and changed only after enough forward samples.

## Full-Market Workflow

1. **Sync and validate.** Read the shared context, recent dated archives, news/announcement indexes, and relevant originals. Use a complete cache only with a timestamp warning if the server fails.
2. **Classify the market.** Use multi-day breadth, turnover, limit-up/broken-limit quality, theme persistence, and core-stock feedback to classify risk-on repair, risk-off, continuation, cash-out, or fresh rotation. Do not infer lifecycle from one snapshot.
3. **Run three independent full-market evidence lanes before narrowing.** Never first choose an active-price pool and then inspect news only inside it.
   - **Message lane:** scan every ordinary tradable stock against the latest week of company filings, reliable news, policy/events, commodity/overseas changes, and public business facts. Include quiet stocks with new hard evidence even when price has not moved.
   - **Market-structure lane:** independently scan every ordinary tradable stock across 5-15 day position, trend, volume/price structure, crowding, distribution, and current tape. Do not require a same-day headline.
   - **Special-setup lane:** independently discover pre-ignition/quiet acceptance, strongest-anchor low-position acceptance, and qualified pin-reversal setups. Run `python analysis/low_pin_reversal_scanner.py --mode overnight --limit 30` for objective pin discovery.
4. **Merge evidence, then form a dynamic verification list.** Deduplicate the three lanes and preserve each stock's evidence path. The intermediate list is not a recommendation pool and must not be fixed at an arbitrary size. In a typical session, compact the merged evidence to roughly 20-30 verification names only after the full-market message and market scans have both run. This prevents missing a flat stock with a fresh catalyst.
5. **Deep-verify the likely final 10-12.** Check catalyst timing, company relevance, 15-day sticky risks, price consumption, next buyer, cash-out supply, and executability. Read originals for the likely top 1-3 and whenever a title is ambiguous, an amount/term matters, or a risk item could veto the trade. A clear structured filing title may support lower-ranked discovery, but never invent missing terms.
6. **Keep low-position ideas evidence-based.** A deep-base/no-news chart stays watch-only; an after-close event can support the next session but not the first board; high-volatility emotion reactivation cannot be called quiet ignition. Upstream/downstream mapping is allowed only at tier 1 or tier 2 with public evidence.
7. **Verify late-session acceptance with available evidence.** Use the latest actual snapshot already available after the request: position versus VWAP/average price, movement toward/away from day high, volume/amount progression, board synchronization, and fake-pull/dive risk. One valid 14:30+ snapshot plus prior intraday evidence can support a qualified judgment; multiple snapshots improve confidence but are not mandatory. Never wait for a future snapshot. If no 14:30+ snapshot exists, label acceptance unconfirmed, reduce confidence/position, and still meet the delivery deadline.
8. **Check risk and executability.** Reject unbuyable sealed boards, unresolved material risk, distribution structures, unverified relevance, and names with no credible next buyer.
9. **Rank eight, execute fewer.** 固定输出八只且代码唯一：前五只来自综合质量排序，第六至第八只来自独立特殊扫描。最终重点通常1-2只、最多3只。弱市仍给完整排序，但只允许触发级股票小仓执行。

## Full-Market and Permission Rules

- Do not use holdings, repeated chat mentions, or user preference to generate the market-wide list.
- Prefer ordinary main-board stocks. Exclude STAR `688/689`, Beijing-style restricted tickers, and other 500K-permission names unless explicitly allowed. Keep default caution on `300/301`.
- Exclude ST/delisting risk and materially untradeable names.
- A sealed or instant limit-up is an anchor/sector flag, not an execution recommendation.
- Candidate pools, `market_score`, `next_day_accept_score`, and similar generated rankings cannot choose the final list.

## Catalyst and Beneficiary Gate

Use this hierarchy, then test whether price has already consumed it:

1. Direct company filing with amount/counterparty/date or material transaction.
2. Policy landing or supply-demand change with clear physical beneficiaries.
3. Industry event with directly verified listed-company relevance.
4. Overseas, commodity, FX, or rate mapping.
5. Repeated old theme, loose concept, or media imagination.

Classify beneficiary type and evidence level:

- `current_hard_logic`: current business/order/revenue/capacity evidence.
- `future_expectation`: sample, certification, expansion, customer validation, or transaction expectation; label it honestly.
- `emotion_front_row`: market-recognized but not hard-logic.
- `pure_concept`: loose label or company denial; reject from execution priority.

同时标记 `tier1_direct`、`tier2_verified` 或 `tier3_concept`。不得乱猜产业链，但也不得把推荐范围缩成主题名称完全一致的制造商。公开客户、项目、订单、扩产用途、正式业务披露或可靠报道可以证明二级硬映射。

Hard news does not override an unbuyable price, absent acceptance, or cash-out risk. Missing company news is not positive evidence.

## Pre-Ignition and Distribution Gate

Search for under-recognized trends with higher lows, controlled volume, MA structure improving, room below the recent high, and theme confirmation. Do not require every candidate to already be above MA20; a low-position stock may be below MA10, but it stays observation-only until a real catalyst/sector/tape trigger appears.

Reject fake quiet structures:

- recent 25%-30% run from swing low without a rebuilt base;
- repeated huge turnover or blow-off volume after large candles/boards;
- long upper shadows, failed seals, open-as-high selling, or late-session VWAP loss;
- a modest green/red candle that is merely self-rescue after distribution;
- high ATR and repeated abnormal-movement/risk filings presented as “stable”.

Large gain is not automatically rejected. 强势股票只要主题、业绩预期、趋势和接力买盘仍在，可以连续推荐；真正否决的是爆量滞涨、长上影、板块退潮、预期兑现完毕或尾盘承接失败。

## Candidate Structure

固定使用以下八只结构：

1. Strongest executable next-day premium setup.
2. Independent replacement with a similarly clear exit path.
3. Main-theme capacity/core or buyable front-row substitute.
4. Under-priced hard-logic/pre-ignition trend.
5. Controlled higher-elasticity or independent backup theme.
6. **企稳点火票**: stable/quiet hard-catalyst or confirmed latent setup that passes anti-distribution gates.
7. **最强涨停逻辑低位承接票**: buyable low-/middle-position extension of the day's strongest unavailable anchor.
8. **低位插针反转票**: a low/middle-position sweep-and-recovery base from today or the latest 1-3 sessions, followed when needed by a current breakout/MACD turn, healthy volume, real 14:30+ acceptance, and a verified next-day discovery path.

Ranks 6-8 are real candidates, not filler. Keep all eight codes unique. If the best pin setup is already in ranks 1-7, move it to rank 8 and replace its former slot. Rank 8 may enter the final 1-3 only after passing shape, message, theme, risk, and late-tape gates. If no setup passes all gates, show the relative-best scanner result as observation-only without inventing execution confidence.

Read [the shared pin-reversal rules](../references/low_pin_reversal.md). The scanner is an objective discovery tool, not a recommendation engine. Inspect `recent_pin_breakouts` first, then same-day `confirmed` and `scouts`. Prefer MACD `red_turn`/`red_expanding`; allow a fast near-cross only after a qualified recent pin plus a current break above the pin high/MA5. Reject high-position self-rescue, negative-announcement pins, extreme-volume distribution, and any candidate that loses VWAP/support after 14:30.

同时运行：

`python analysis/market_leadership_scanner.py --mode overnight --limit 40`

用它补充健康强趋势、分歧承接和启动前候选，但不得用价格结构替代消息、产业链、风险和下一买家验证。

## Timing Discipline

Start immediately when asked; do not wait for a fixed clock time or a future snapshot. Use the latest complete, time-valid data already available.

Set the response deadline before analysis:

- target a complete answer within 15 minutes of the request;
- hard-stop analysis at 20 minutes;
- when asked at or before 14:30, deliver the formal actionable answer no later than 14:50, preferably by 14:45-14:48;
- when asked after 14:30, use the earlier of `request time + 20 minutes` and the last realistically tradable decision point. If little time remains, immediately use degraded mode: latest complete cache, fewer executable names, explicit uncertainty, and no repeated tool calls.

Use this default time budget as a guardrail, not as a reason to delay:

1. 0-2 minutes: one incremental sync and data-health/calendar gate.
2. 2-6 minutes: market regime plus three full-market evidence lanes using compact local indexes.
3. 6-11 minutes: merge/deduplicate, risk vetoes, and narrow to likely final 10-12.
4. 11-15 minutes: verify final evidence, next buyer, acceptance, entry/exit, write journal, and answer.
5. 15-20 minutes: contingency reserve only for a material ambiguity in a top candidate, never for broader re-search.

对前三个主题进行一次批量外部核查，补充最近七天的官方政策、公司IR、可靠产业新闻、海外资本开支和供需变化。搜索是主题发现与交叉验证的一部分，不只在服务器失败时使用。控制为一次批量查询，优先验证前两名和重大否决风险，不陷入重试链。

After the formal answer, allow only a brief cancellation update for a sudden dive, fake pull-up, VWAP/support loss, new risk filing, or broken theme synchronization. Do not rerank or rescan the full market. Never claim late-session acceptance from an earlier snapshot without labeling the limitation.

## Output Contract

Write concise Chinese and include:

- calendar header: current time, latest completed trading day, exact next trading day, extra closed nights;
- data scope and limitations, including actual late-session snapshot coverage;
- market regime, theme lifecycle, and next-day capital path;
- 严格八只：前五主候选加第六至第八特殊席位；
- for each: code/name, current price/change, evidence type, catalyst timestamp class, theme role, multi-day structure, late-session acceptance, announcement-risk result, next buyer, premium/exit type, buy area/trigger, abandon condition, position, and next-day sell plan;
- rank 6/7 labels;
- rank 8 `低位插针反转票` with pattern date, confirmation date/days since pin, low/recovery, range position, shadow/close position, pattern/current amount, MACD state, message/theme confirmation, next buyer, trigger, invalidation, position, and next-day exit;
- 最终重点1-2只，只有逻辑独立且证据充分时才允许第3只；
- 弱市标注“小仓触发”或“观察级”，但仍给出完整八只排序。

Read [strategy reference](references/strategy.md) for detailed scoring, lifecycle edge cases, and examples. Load only the industry material needed to verify a top theme or candidate; Serenity or other research files are knowledge supplements, never the candidate pool.

## Mandatory Recommendation Journal

Before sending the final answer, seal the final eight-stock plan in `data_recommendations/daily_recommendations.json` with:

`python analysis/recommendation_journal.py record --mode overnight --trade-date YYYY-MM-DD --input tmp/overnight_recommendation.json`

Use the buy-date as `trade-date`. The input must contain `decision_time`, `market_judgment`, `data_context`, exactly eight `candidates`, `focus_codes`, `no_trade`, and `response_summary`. Each candidate must include rank/code/name plus catalyst/time class, theme role, current/reference price, late-session acceptance, next buyer, entry trigger/range, abandon condition, position, risk flags, premium type, and next-trading-day sell plan. Ranks 6-8 must set `slot_type` to `stabilization_ignition`, `strong_anchor_low_position_acceptance`, and `low_pin_reversal` respectively. Rank 8 must retain objective pin/MACD evidence and confirmation grade.

Do not edit or delete a sealed run after outcomes are known. A revised recommendation creates a new run; the journal preserves the earlier version and marks it superseded. If journaling fails, state that failure in the final answer instead of pretending it was recorded.

临时JSON、网页下载和PDF只能放在`tmp/`，记录完成后删除，不得加入Git。

## Next-Day Sell Discipline

- High open that cannot continue in 5-10 minutes: sell/reduce.
- Flat/small-low open that repairs: use the first strong rush unless both stock and theme confirm continuation.
- Low open that cannot turn red or reclaim support in 10-15 minutes: exit.
- Hold past morning only above VWAP/key support with continuing theme and non-distribution volume.
- Near-limit rush that cannot seal: sell at least half, usually all for this strategy.
- Fast sealed board: hold only while sealed; open and fail to reseal means sell.
- Do not carry beyond the next trading day.
