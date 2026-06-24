---
name: morning_stock_picker
description: 'Use this skill for a pre-market, auction, or opening-session A-share stock-picking plan: independently scan the full ordinary tradable market, rank eight candidates including quiet-ignition, strongest-theme low-position acceptance, and low-position pin-reversal setups, report relevant overseas conditions and confirmed-holding actions, and deliver a time-bounded execution plan from server-backed news and market data.'
---

# Morning Stock Picker

Build a probability-based morning trading plan, not a promise. Select independently from the full ordinary tradable A-share market. Output exactly eight unique candidates and identify only the best 1-2 as execution priorities.

## Non-Negotiable Boundaries

- The server only collects and organizes objective data. Make all theme, catalyst, risk, timing, and ranking judgments locally.
- Do not use holdings, chat history, or user preference to generate new-stock candidates.
- Use `data_portfolio/current_holdings.json` as the only persistent holdings source. Holdings affect exposure and sell discipline, never candidate generation.
- Do not invoke industry-chain research or infer upstream/downstream beneficiaries. Keep those resources stored but disabled during recommendation runs.
- Verify company relevance through an original announcement, reliable report, or public company disclosure. Label expectation trades as expectations.
- Default to ordinary main-board A shares. Exclude `688/689`, Beijing Stock Exchange/restricted names, ST/delisting-risk names, and other 500K-threshold securities. Treat `300/301` cautiously unless the user explicitly permits them.
- Never promise a limit-up. Use conditional language and abandon the trade when its trigger fails.

## One-Sync Data Rule

At the start of a live request, run exactly once:

`venv/bin/python skills/morning_stock_picker/scripts/server_context.py`

This command performs incremental synchronization into the shared `data_server_cache`; do not run it again during the same recommendation. Verify mode, calendar, health, snapshot time/completeness, history coverage, counts, cache fallback, and sync age from its compact output and `data_server_cache/latest_context.json`.

Use the referenced compressed features, pools, recent-history files, news index, and announcement index. Query/narrow objective rows locally; never load a full-market raw JSON into conversation context. Fetch original news or announcement text by ID only for finalists or unresolved material risks.

If synchronization fails, use the newest complete shared cache when still decision-relevant, state its timestamp/age, and lower confidence. Do not run local collectors, create skill-specific caches, or read `data_dev`/local `data_market` as substitutes.

## Delivery Contract

Quality comes from disciplined narrowing, not unlimited analysis time.

- Target a formal answer within 12-15 minutes; 20 minutes is the hard maximum.
- Freeze the primary evidence cutoff after the one sync completes. Use auction/opening data already available at that cutoff; do not wait for the next market stage or repeatedly refresh.
- A request before 9:15 must receive a complete `竞价前预案`; never wait for 9:15 or 9:25.
- A request during auction uses the latest completed auction observation already available; do not wait for 9:25.
- A request after the open uses the latest available opening snapshot; do not delay for another 5/10-minute candle.
- If fresh critical news arrives while writing and is already present locally, incorporate it once. Do not restart the full scan.
- When the hard maximum is reached, finish from verified evidence already collected, mark unresolved candidates as observation-only, and never invent missing facts.
- External source-gap lookup is fallback-only for a leading candidate or material risk. Make one targeted attempt; on failure, continue from server evidence and disclose the gap.

## Time-Bounded Workflow

### Stage 1: Data and regime, about 2-3 minutes

1. Run the single incremental sync and validate its compact result.
2. Read confirmed holdings and the newest server-backed news/announcement indexes.
3. Classify the morning regime as risk-on, weak repair, rotation, risk-off, retreat, or consensus cash-out.
4. Before auction, use overnight markets plus the latest completed A-share session. During auction/opening, add only data already available.

### Stage 2: Full-market evidence list, about 3-4 minutes

Scan the full ordinary tradable market through three independent lanes, then merge and deduplicate to roughly 30-50 objective evidence names:

1. `Message lane`: fresh company announcements, policy landing, orders, price/supply-demand changes, scheduled events, overseas/commodity/FX/rate catalysts, and continuing one-week themes.
2. `Market lane`: full-market relative strength, liquidity, 5-15 day structure, controlled volume, prior money traces, low/middle position, and absence of obvious distribution.
3. `Special-setup lane`: quiet ignition, strongest-theme buyable low-position acceptance, and low-position pin/MACD reversal.

Candidate pools and rankings are discovery tools, not the final answer. A stock outside a generated pool remains eligible when direct evidence and current market confirmation are stronger.

### Stage 3: Narrow and verify, about 5-6 minutes

1. Merge evidence and veto lists into 20-30 candidates.
2. Apply tradability, news timing, 5-15 day distribution, gap/兑现, announcement-risk, and buyability filters.
3. Deep-check only the top 10-12 names. Fetch originals for the likely top 1-3 and for any unresolved material risk; use indexed direct evidence for the rest.
4. Identify the likely next buyer and realistic opening purchase window for every execution-level name.
5. Check relevant overseas benchmarks once, in one batch, only for finalist themes and confirmed holdings.

### Stage 4: Decide and record, about 2-3 minutes

1. Rank exactly eight unique candidates using evidence strength, under-pricing, market confirmation, tradability, next-buyer clarity, and exit quality.
2. Evaluate confirmed holdings separately with immediate action rules.
3. Write the concise Chinese answer.
4. Seal the exact plan in the recommendation journal before sending.

Do not repeat a full-market scan, news scan, overseas check, or server synchronization after a later stage begins.

## Evidence and Timing Rules

Morning selection is message-first, while market structure decides execution.

- Fresh direct company catalyst > policy landing > industry event with directly verified companies > overseas/commodity/rate mapping > repeated old theme.
- Prior-day strength validates recognition and liquidity but cannot independently anchor a recommendation.
- Classify material catalysts as `盘前未交易 / 同日已交易 / 盘后新发 / 涨停后补发`. Downgrade post-board explanations and already fully priced news.
- Distinguish week-long continuing themes from one-day messages. A continuing theme still needs current freshness or auction/opening confirmation.
- A hard catalyst may remain a candidate despite a weak sector, but cannot become an execution priority without relative strength and demand confirmation.
- One-word or sealed limit-up names are theme flags, not buy recommendations.

## Auction and Opening Modes

### Before 9:15

Label the answer `竞价前盘前预案`. Rank eight provisional candidates from fresh messages, overnight conditions, and completed A-share data. Give explicit 9:15/9:25/9:30 confirmation and cancellation triggers, but do not claim auction confirmation.

### 9:15-9:30

Use only the latest auction observation already available. Confirm or veto the pre-market logic through gap size, auction amount, cancellation behavior when available, buyability, and theme synchronization. Do not wait for a later auction checkpoint.

### After 9:30

Use available open/early-tape data: VWAP or average-price position, relative strength, sector breadth, opening-as-high risk, and second-volume-push quality. Define the first action within five minutes and reevaluate within ten minutes rather than issuing retrospective instructions.

## Candidate Structure

1. Ranks 1-5: main candidates ordered by executable risk-reward, not story excitement.
2. Rank 6 `企稳点火票`: flat/modestly strong, directly supported, and capable of repricing. Reject recent 25%-30% runs, repeated huge turnover, post-limit failure, long upper shadows, or an opening-as-high selloff unless a multi-session base has clearly rebuilt.
3. Rank 7 `最强涨停逻辑低位承接票`: use the strongest recognized/limit-up theme as an anchor, then choose a buyable low/middle-position stock only with direct public relevance and current market confirmation.
4. Rank 8 `低位插针反转票`: run once after sync:

   `venv/bin/python analysis/low_pin_reversal_scanner.py --mode morning --limit 30`

   Inspect only the leading rows needed for rank 8. Read [shared pin-reversal rules](../references/low_pin_reversal.md). Prefer the previous completed session and allow at most three completed sessions while the base remains valid. Require low/middle position, a swept low with effective recovery, healthy amount, MACD `red_turn`/`red_expanding` or a rapidly contracting histogram, plus message/theme/risk and available auction/opening confirmation. Technical shape alone is observation-only.

Ranks 6-8 are real candidates and may outrank ranks 3-5 when their execution quality is better. If a special setup lacks a required gate, label it `观察级` and exclude it from the final focus pair.

## Hard Vetoes

Reject or downgrade:

- major negative announcement, unresolved reduction, regulatory/investigation, litigation, fraud, delisting, or severe performance risk;
- loose social-media concepts or company-denied stories;
- prior blow-off, heavy-volume bearish candle, repeated high turnover, long upper shadow, failed limit-up, high-position stagnation, or obvious profit-inventory pressure;
- news value already consumed by a large gap without VWAP/sector/second-push support;
- no identifiable next buyer or no realistic exit window;
- stale/incomplete objective data that cannot support an executable decision.

Keep material risk announcements active for 15 calendar days unless a newer original filing resolves them.

## Overseas and Holdings

After the finalist themes exist, check only directly relevant US/HK sectors, representative assets, commodities, futures, FX, or rates. Record timestamp and whether the quote is closed, live, or indicative. Use `利多 / 中性 / 利空 / 无可靠映射`; correlation is not proof.

Before new-stock ranks, output every confirmed holding as `留 / 减 / 卖 / 禁止加仓`, with overseas impact where relevant, first action trigger, price/VWAP invalidation, and latest reevaluation. Never justify holding with cost price or `再看看`. Adverse overseas mapping plus weak A-share confirmation requires action at the first failed repair.

Only update the ledger after the user explicitly confirms a buy, add, partial sale, full sale, or correction. Never infer trades from recommendations.

## Ranking and Execution

Rank by practical tradability:

`direct catalyst + freshness + under-pricing + market confirmation + 5-15 day structure + next buyer + exit quality - distribution/risk/兑现`

- Gap 0%-3%: normally comfortable when amount and theme confirm.
- Gap 3%-5%: wait for a hold/retest and second push.
- Gap 5%-7%: default priced-in/兑现 test in weak or rotating markets.
- Gap 7%-9%: high兑现 risk; normally do not chase.
- Small low open -1% to -3%: eligible only after quick repair with theme confirmation.
- Below -4%: default abandon unless a very hard catalyst receives immediate strong repair.

Ranks 1-2 must pass both buyer/exit and drawdown/cash-out gates. In a weak market, focus only one name or do not trade. Do not change factor weights from a handful of outcomes; use the recommendation journal for forward validation.

## Required Chinese Output

Keep the answer compact and decision-oriented:

1. `数据口径与市场总判断`: cutoff, auction/opening mode, market regime, current message themes, and yesterday-line continuation/divergence/fade judgment.
2. `相关外围板块行情`: only finalist and holding themes, with benchmark, move, timestamp, impact, and affected codes.
3. `持仓早盘处置`: show ledger update time and actions, or state no confirmed holdings.
4. `8只排名`: for each give code/name, role, direct evidence, reference/current price, auction/opening condition, buy trigger, abandon condition, suggested position, next buyer, and sell discipline.
5. For rank 8 also give pattern date, pin low/recovery, range position, amount, MACD state, confirmation grade, and invalidation.
6. `最终执行`: only 1-2 focus names, key no-buy conditions, aggregate exposure, and `不交易` when confidence is insufficient.

## Mandatory Recommendation Journal

Before sending, record the exact final plan:

`venv/bin/python analysis/recommendation_journal.py record --mode morning --trade-date YYYY-MM-DD --input /tmp/morning_recommendation.json`

The input must include `decision_time`, `market_judgment`, `data_context`, `overseas_sector_context`, `holding_actions`, exactly eight `candidates`, `focus_codes`, `no_trade`, and `response_summary`. Preserve each candidate's actual evidence, time class, price, confirmation, trigger, abandon condition, position, risks, next buyer, and sell discipline. Rank 8 must preserve objective pin/MACD evidence.

Never rewrite a sealed run after outcomes are known. A revision creates a new run. If journaling fails, disclose the failure.
