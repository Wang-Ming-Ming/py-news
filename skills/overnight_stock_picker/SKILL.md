---
name: overnight_stock_picker
description: 'Use when the user asks for a late-session A-share overnight plan, normally from 14:30 onward: scan the full ordinary tradable market, rank eight candidates including a dedicated low-position pin-reversal/MACD-turn stock, identify only the best 1-3 executable names, and provide a next-trading-day exit plan using fresh news/announcements, multi-day market structure, real late-session acceptance, announcement risk, and next-buyer logic.'
---

# Overnight Stock Picker

Recommend eight ranked ordinary A-share candidates for buying late in the session and selling no later than the next trading day. The primary objective for ranks 1-2 is not maximum theoretical upside; it is a realistic positive/red exit window after the user's cost, supported by a clear next buyer.

Never promise a rise or limit-up. Separate research quality from execution quality and say when no normal-size trade exists.

## Data and Calendar Gate

Run first:

`venv/bin/python skills/overnight_stock_picker/scripts/server_context.py`

All stock skills share `data_server_cache/` and `latest_context.json`. Verify:

- context mode, server time, calendar, latest valid snapshot time;
- expected/actual counts, completeness, `using_cached_data`, and sync error;
- at least 3 and preferably 5-15 recent trading-day archives;
- availability of actual 14:30-15:00 snapshots versus historical-close-only data.

Use only server-backed objective data. Fetch relevant news/announcement originals by ID. The server never decides themes, hard logic, lifecycle, risks, candidates, or rankings; Codex does.

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
3. **Build direct evidence paths.** Start from fresh company news, policy/industry events, commodity/overseas mapping, confirmed themes, directly verified beneficiaries, and market-led front-row stocks. Do not load optional industry research or derive upstream/downstream substitutes during a live recommendation.
4. **Scan the full ordinary tradable market.** Search main-board stocks for directly supported beneficiaries, buyable front-row names, pre-ignition trends, quiet acceptance, and low-position theme extensions. Do not start from a generated candidate pool.
5. **Keep low-position ideas evidence-based.** A deep-base/no-news chart stays watch-only; an after-close event can support the next session but not the first board; high-volatility emotion reactivation cannot be called quiet ignition. Do not reverse-map upstream/downstream peers from an anchor stock.
6. **Verify late-session acceptance.** Use the actual observed 14:30 onward snapshots: position versus VWAP/average price, movement toward/away from day high, volume/amount progression, board synchronization, and final-minute fake-pull or dive. Historical close-only data cannot prove this gate.
7. **Check risk and executability.** Reject unbuyable sealed boards, unresolved material risk, distribution structures, unverified relevance, and names with no credible next buyer.
8. **Scan the dedicated pin-reversal lane.** Run `venv/bin/python analysis/low_pin_reversal_scanner.py --mode overnight --limit 30`, then verify the relative-best setup against fresh messages, theme strength, risk, and actual 14:30+ acceptance.
9. **Rank eight, execute fewer.** Output eight unique stocks for comparison, but select normally 1-2 and at most 3. Weak/no-edge markets allow one tiny trial or no trade.

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

Classify beneficiary type:

- `current_hard_logic`: current business/order/revenue/capacity evidence.
- `future_expectation`: sample, certification, expansion, customer validation, or transaction expectation; label it honestly.
- `emotion_front_row`: market-recognized but not hard-logic.
- `pure_concept`: loose label or company denial; reject from execution priority.

Hard news does not override an unbuyable price, absent acceptance, or cash-out risk. Missing company news is not positive evidence.

## Pre-Ignition and Distribution Gate

Search for under-recognized trends with higher lows, controlled volume, MA structure improving, room below the recent high, and theme confirmation. Do not require every candidate to already be above MA20; a low-position stock may be below MA10, but it stays observation-only until a real catalyst/sector/tape trigger appears.

Reject fake quiet structures:

- recent 25%-30% run from swing low without a rebuilt base;
- repeated huge turnover or blow-off volume after large candles/boards;
- long upper shadows, failed seals, open-as-high selling, or late-session VWAP loss;
- a modest green/red candle that is merely self-rescue after distribution;
- high ATR and repeated abnormal-movement/risk filings presented as “stable”.

Large gain is not automatically rejected. It ranks high only when incremental relay demand is specific and stronger than available profit inventory.

## Eight-Candidate Structure

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

## Timing Discipline

Start when asked, normally around 14:30. Use the latest valid data and aim to deliver the actionable plan around 14:45-14:50, preferably by 14:52. Use 14:55 only for cancellation checks such as a sudden dive, fake pull-up, VWAP loss, or broken sector synchronization.

Never wait for a fixed minute when enough valid evidence already exists. Never claim late-session acceptance from a snapshot earlier than the observed window.

## Output Contract

Write concise Chinese and include:

- calendar header: current time, latest completed trading day, exact next trading day, extra closed nights;
- data scope and limitations, including actual late-session snapshot coverage;
- market regime, theme lifecycle, and next-day capital path;
- exactly eight ranked candidates;
- for each: code/name, current price/change, evidence type, catalyst timestamp class, theme role, multi-day structure, late-session acceptance, announcement-risk result, next buyer, premium/exit type, buy area/trigger, abandon condition, position, and next-day sell plan;
- rank 6/7 labels;
- rank 8 `低位插针反转票` with pattern date, confirmation date/days since pin, low/recovery, range position, shadow/close position, pattern/current amount, MACD state, message/theme confirmation, next buyer, trigger, invalidation, position, and next-day exit;
- conservative 1-2 stock plan and aggressive maximum-3 plan only when justified;
- explicit “small trial/no normal trade” statement when confidence is insufficient.

Read [strategy reference](references/strategy.md) only for detailed scoring, lifecycle edge cases, and examples. Do not load optional industry-research resources during a normal recommendation run.

## Mandatory Recommendation Journal

Before sending the final answer, seal the final eight-stock plan in `data_recommendations/daily_recommendations.json` with:

`venv/bin/python analysis/recommendation_journal.py record --mode overnight --trade-date YYYY-MM-DD --input /tmp/overnight_recommendation.json`

Use the buy-date as `trade-date`. The input must contain `decision_time`, `market_judgment`, `data_context`, exactly eight `candidates`, `focus_codes`, `no_trade`, and `response_summary`. Each candidate must include rank/code/name plus catalyst/time class, theme role, current/reference price, late-session acceptance, next buyer, entry trigger/range, abandon condition, position, risk flags, premium type, and next-trading-day sell plan. Rank 8 must also preserve its objective pin/MACD evidence and confirmation grade.

Do not edit or delete a sealed run after outcomes are known. A revised recommendation creates a new run; the journal preserves the earlier version and marks it superseded. If journaling fails, state that failure in the final answer instead of pretending it was recorded.

## Next-Day Sell Discipline

- High open that cannot continue in 5-10 minutes: sell/reduce.
- Flat/small-low open that repairs: use the first strong rush unless both stock and theme confirm continuation.
- Low open that cannot turn red or reclaim support in 10-15 minutes: exit.
- Hold past morning only above VWAP/key support with continuing theme and non-distribution volume.
- Near-limit rush that cannot seal: sell at least half, usually all for this strategy.
- Fast sealed board: hold only while sealed; open and fail to reseal means sell.
- Do not carry beyond the next trading day.
