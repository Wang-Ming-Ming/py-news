---
name: morning_stock_picker
description: 'Use this skill for a pre-market, auction, or opening-session A-share stock-picking plan: independently scan the full ordinary tradable market, rank zero to eight regular candidates plus one optional strict ninth-slot emerging-theme stock, report relevant overseas conditions and confirmed-holding actions, and deliver a time-bounded execution plan from server-backed news and market data.'
---

# Morning Stock Picker

Build a probability-based morning trading plan, not a promise. Select independently from the full ordinary tradable A-share market. Output zero to eight regular research candidates according to actual quality plus one optional dedicated ninth-slot emerging-theme candidate, identify at most two provisional priorities before auction, and promote only actually confirmed names to execution focus. Never fill either the regular list or slot 9 as a quota.

## Non-Negotiable Boundaries

- The server only collects and organizes objective data. Make all theme, catalyst, risk, timing, and ranking judgments locally.
- Do not use holdings, chat history, or user preference to generate new-stock candidates.
- Use `data_portfolio/current_holdings.json` as the only persistent holdings source. Holdings affect exposure and sell discipline, never candidate generation.
- Do not invoke broad industry-chain research or infer upstream/downstream beneficiaries from a fashionable anchor. Use the [emerging-theme discovery rules](../references/theme_discovery.md) to build only a narrow registry of directly verified companies after a theme seed has independent evidence.
- Verify company relevance through an original announcement, reliable report, or public company disclosure. Label expectation trades as expectations.
- A newly published article is not necessarily new information. For every execution-level catalyst, identify when the underlying fact was first disclosed. Repackaged interaction-platform answers, repeated annual-report language, and media rewrites of an older fact cannot be treated as a new morning catalyst.
- `首推` is a separate permission, not the first item in a long list. It requires an A-grade catalyst, a primary-source check, at least a 120-day matching-fact lookback, explicit counterevidence, realistic economic magnitude, market confirmation, buyability, and T+1 survivability. If any item is missing, output `今日无首推`; never soften the missing evidence with a high score.
- Default to ordinary main-board A shares. Exclude `688/689`, Beijing Stock Exchange/restricted names, ST/delisting-risk names, and other 500K-threshold securities. Treat `300/301` cautiously unless the user explicitly permits them.
- Never promise a limit-up. Use conditional language and abandon the trade when its trigger fails.
- Respect A-share T+1 settlement. A newly opened position cannot be sold the same day, so an `intraday-only`, same-day stop-dependent, or opening-spike setup is not eligible for a new-buy recommendation. Every executable name must survive an overnight-risk gate and include a realistic next-session exit plan.
- Separate `盘前优先观察` from `已确认可执行`. Before auction/opening confirmation, execution `focus_codes` must remain empty; use `provisional_focus_codes` for at most two names. A trigger that never prints is `未触发/未交易`, not a failed or successful recommendation.
- Resolve every stock to one canonical `code + exact name` pair before researching it. Similar names are not interchangeable, and a name/code mismatch invalidates the thesis.
- Never use a later announcement to claim an earlier recommendation could have known the catalyst. Preserve whether the public fact was available at the decision cutoff and label pre-disclosure price action separately.

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
2. Run the dynamic novelty radar once:

   `venv/bin/python analysis/emerging_theme_radar.py --as-of DECISION_TIME --recent-hours 72 --baseline-days 21 --limit 12`

   Read [emerging-theme discovery](../references/theme_discovery.md). Keep only terms with a concrete causal variable; broad article volume is not enough.
3. Read confirmed holdings and the newest server-backed news/announcement indexes.
4. For the leading 1-3 emerging terms, verify overseas company/policy/supply evidence and direct A-share mapping. Use one batched external lookup only when the local feed lacks the original source.
5. Check live overseas shock indicators available at the cutoff, especially Japan/Korea/Taiwan technology indices, semiconductor benchmarks, directly relevant commodities, and index futures. A synchronized external selloff is a risk veto, not a stock-picking theme.
6. Classify the morning regime as risk-on, weak repair, rotation, risk-off, retreat, or consensus cash-out.
7. Before auction, use overnight markets plus the latest completed A-share session. During auction/opening, add only data already available.

### Stage 2: Full-market evidence list, about 3-4 minutes

Scan the full ordinary tradable market through four independent lanes, then merge and deduplicate to roughly 30-50 objective evidence names:

1. `Theme/message lane`: start from the dynamic theme registry, then add fresh company announcements, policy landing, orders, price/supply-demand changes, scheduled events, overseas/commodity/FX/rate catalysts, and continuing one-week themes.
2. `Market lane`: full-market relative strength, liquidity, 5-15 day structure, controlled volume, prior money traces, low/middle position, and absence of obvious distribution.
3. `Special-setup lane`: quiet ignition, strongest-theme buyable low-position acceptance, and low-position pin/MACD reversal.
4. `First-board radar lane`: prior-session pre-activation plus current opening confirmation. Look for controlled abnormal activity near a new range high, established theme memory, modest market capitalization, and a buyable flat/small-low opening that rapidly repairs and joins a live theme. Without a public catalyst this lane is opening-session observation only, never a pre-market priority.

Candidate pools and rankings are discovery tools, not the final answer. A stock outside a generated pool remains eligible when direct evidence and current market confirmation are stronger.

For every finalist, preserve `canonical code/name`, `selection model`, `publication time`, `underlying fact first-disclosure time`, `publicly available at decision cutoff`, `original source type`, and `economic magnitude or narrative discontinuity`. A contract amount, price change, order volume, profit effect, capacity utilization, transfer of an entire operating business, or other verifiable transmission path is preferable to a qualitative label.

### Stage 3: Narrow and verify, about 5-6 minutes

1. Merge evidence and veto lists into 20-30 candidates.
2. Apply tradability, news timing, 5-15 day distribution, gap/兑现, announcement-risk, and buyability filters.
3. Apply the `big-move thesis gate` before scoring. Assign each finalist to one primary model:
   - `earnings_repricing`: a genuine new fact has a measurable path to revenue, profit, product price, utilization, supply scarcity, or valuation;
   - `narrative_identity_jump`: an original company filing verifiably changes the operating boundary or market identity, such as acquiring a complete hot-industry business with assets, team, intellectual property, and contracts. This model does not pretend near-term earnings exist; it requires an already active theme, small/mid-cap price elasticity, market confirmation, and much tighter execution risk.
   Both models require remaining repricing room, a concrete next-buyer group, buyability, and T+1 survivability.
   A no-new-information `first_board_radar` name is not a third thesis model. Before the open it remains observation-only. After the open it may become at most a secondary, small-position execution candidate only when the verified old theme is currently active, the stock repairs a flat/small-low opening, breaks the prior attack high on controlled volume, and remains buyable; otherwise it is not traded.
   A candidate that failed its catalyst/relative-strength thesis in the previous session enters a three-session cooldown. It cannot be recommended again merely because it is lower; only a genuinely new official fact plus fresh auction/opening reversal confirmation can end the cooldown.
4. Deep-check only the top 10-12 names. Fetch originals for the likely top 1-3 and for any unresolved material risk; use indexed direct evidence for the rest. For every proposed focus name, search backwards for the same underlying fact. The proposed primary pick requires at least a 120-day lookback across announcements, annual reports, interaction replies, and reliable news.
5. Identify the likely next buyer and realistic opening purchase window for every execution-level name.
6. Reconcile finalist themes with the earlier overseas/theme check; do not run a second broad search. Check an additional benchmark only when a finalist or holding introduces a genuinely new exposure.

### Stage 4: Decide and record, about 2-3 minutes

1. Rank zero to eight unique research candidates, but keep execution status separate. Stop when quality runs out; never add filler to reach eight.
2. Evaluate exactly one optional `第9只新题材专席` under the strict gate in [emerging-theme discovery](../references/theme_discovery.md). If any required evidence is missing, keep `new_theme_candidate` null and state that the slot is empty.
3. Evaluate confirmed holdings separately with immediate action rules.
4. Before auction, publish at most two `盘前优先观察` names and no executable focus. During auction/opening, only names whose stated trigger has actually occurred may enter `focus_codes`.
5. Grant or deny `首推` separately. Before confirmation it may only be regular rank 1 or the independently qualified slot 9. After confirmation, a lower-ranked name can become first only when new auction/opening evidence is recorded and is stronger than the original leader.
6. Write the concise Chinese answer.
7. Seal the exact plan in the recommendation journal before sending.

Do not repeat a full-market scan, news scan, overseas check, or server synchronization after a later stage begins.

## Primary-Pick Constitution

The user's likely first trade carries more downside than an ordinary research candidate. Apply these rules before using `首推`, `第一选择`, or equivalent wording:

1. Classify freshness as exactly one of `new_material_fact`, `new_certainty_upgrade`, `new_external_causal_shock`, or `scheduled_repricing`. A fresh article containing an old fact is `stale_republication` and cannot enter provisional or executable focus.
2. Record both the newest article time and the earliest matching underlying disclosure found in at least a 120-day lookback. State what changed between them. `Nothing economically or legally changed` is an automatic veto.
3. Require materiality grade A. At minimum, verify an order/contract amount, revenue or profit path, price/supply shock, utilization change, complete operating-identity change, or a new external event with direct company transmission. A supplier designation, certification, sample, interaction reply, or `有望受益` without order volume and conversion schedule cannot be grade A.
4. Read counterevidence before ranking: business exclusions, tiny current revenue, prior disclosure, clarification, execution conditions, dilution, recent gains, and weak relative strength. Include the strongest negative fact in the journal.
5. Keep the primary pick aligned with execution order. Before confirmation, a rank 6-8 special setup can never leapfrog rank 1. After auction/opening, any non-rank-1 promotion requires written evidence of stronger theme breadth, relative strength, VWAP/average-price support, and a buyable second push.
6. When the latest completed market breadth is below 30% or the regime is risk-off, issue no pre-confirmation primary pick. Only a triggered counter-trend theme core may become primary, with initial position at most 5%; otherwise say `今日无首推/不交易`.
7. A primary pick may be null. Having no first recommendation is a valid decision and is preferable to converting a secondary idea into a forced lead.

## Evidence and Timing Rules

Morning selection is message-first, while market structure decides execution.

- Discover and stage the theme before ranking its stocks: `seed / emerging / confirmed / acceleration / overheat / retreat`. An emerging physical bottleneck with independent overseas and A-share evidence outranks a stale individual-company headline.
- Overseas company backlog, capacity, lead time, customer agreements, export licensing, and physical prices can seed a theme. Broad overseas index movement cannot.
- Within an emerging/confirmed theme, scan new-business filings for acquisitions, joint ventures, business/team/IP/contract transfers, and funded capacity projects. Separate operating control from passive investment or business-scope registration.
- Fresh direct company catalyst > policy landing > industry event with directly verified companies > overseas/commodity/rate mapping > repeated old theme.
- Judge freshness by the first disclosure of the underlying fact, not by the timestamp of the latest article. An interaction-platform answer that repeats an annual report or an older reply is stale.
- Signed orders with measurable economics, confirmed price/supply changes, and material earnings revisions rank above intended investment, generic capacity construction, supplier qualification without order volume, or qualitative business progress.
- A known tender becoming a formally signed contract can be `new_certainty_upgrade`, but disclose the original tender date and explain the incremental legal/economic certainty. Do not call the entire contract amount newly discovered. An article merely repeating an annual-report sentence is never such an upgrade.
- Planned capex and completed capacity are not automatically positive catalysts: require evidence of demand, utilization, customer orders, pricing, or profit conversion.
- Small insider purchases, routine generic-drug registrations, early clinical-trial approvals, completion of an already announced acquisition, and exchange-listing ceremonies are not big-move catalysts by themselves. H-share issuance/listing and other new-share supply events are dilution/overhang risks unless price action proves otherwise.
- Preserve a `failed_thesis_cooldown` flag. A stock that ignored a positive catalyst, failed its trigger, or materially underperformed its active theme yesterday cannot be recycled as today's low-position opportunity.
- Prior-day strength validates recognition and liquidity but cannot independently anchor a recommendation.
- Classify material catalysts as `盘前未交易 / 同日已交易 / 盘后新发 / 披露前异动 / 涨停后补发`. Downgrade post-board explanations and already fully priced news. A later disclosure can explain continuation but can never be backfilled as the cause known before the first move.
- Distinguish week-long continuing themes from one-day messages. A continuing theme still needs current freshness or auction/opening confirmation.
- A hard catalyst may remain a candidate despite a weak sector, but cannot become an execution priority without relative strength and demand confirmation.
- One-word or sealed limit-up names are theme flags, not buy recommendations.
- Narrative-identity events must be separated from earnings events in wording and scoring. A framework agreement with tiny current revenue may create short-term label repricing, but it cannot be described as material profit contribution.

## Auction and Opening Modes

### Before 9:15

Label the answer `竞价前盘前预案`. Rank zero to eight provisional candidates from fresh messages, overnight conditions, and completed A-share data. Give explicit 9:15/9:25/9:30 confirmation and cancellation triggers, but do not claim auction confirmation. Use `provisional_focus_codes`; `focus_codes` must be empty. A first-board-radar name without a new public fact cannot enter `provisional_focus_codes`.

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

Ranks 6-8 are research candidates, not shortcuts into the focus pair. Before auction they cannot outrank the main candidates merely because they are low-position or theoretically capable of ignition. They may enter the focus pair only after stronger real-time theme and stock confirmation than the current top-ranked executable name. If a special setup lacks a required gate, label it `观察级`.

`首板异动雷达` is a selection tag rather than a fixed rank. It must record the prior attack high, close retention, turnover/volume-ratio band, market capitalization, old-theme evidence, current theme breadth, opening repair, and breakout status. Without a new public fact it cannot be ranked as pre-market focus or the sole first execution priority.

5. Optional slot 9 `新题材专席`: separate from ranks 1-8. It requires an `emerging` or `confirmed` specific theme, at least two independent evidence events, a verified primary source, overseas hard causality, direct A-share company evidence, market confirmation, buyability, and T+1 survivability. Never use a `seed`, denial, loose mapping, generic broad theme, or sealed board. When absent, explicitly output `第9只：空缺（无合格新题材）`.

## Hard Vetoes

Reject or downgrade:

- major negative announcement, unresolved reduction, regulatory/investigation, litigation, fraud, delisting, or severe performance risk;
- unresolved stock identity or a code/name mismatch;
- loose social-media concepts or company-denied stories;
- a catalyst disclosed after the decision cutoff when it is being used to justify an earlier entry;
- an interaction reply or media article that repeats an annual report, prior announcement, or older interaction fact without new amount, customer commitment, conversion schedule, price, profit, or legal certainty;
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

`model fit + direct evidence + freshness/public availability + under-pricing + market confirmation + 5-15 day structure + next buyer + exit quality - distribution/risk/兑现`

- Run the big-move thesis gate before assigning a numerical score. A high score cannot compensate for stale facts, a missing earnings path under `earnings_repricing`, a non-material identity change under `narrative_identity_jump`, or absent market recognition.
- A narrative-identity candidate is never promoted merely because the acquired industry label is fashionable. Require direct ownership/operating control evidence, an active market theme, and a buyable first/second-board window. If it is already sealed at the limit or under exchange focus after repeated boards, use it only as a theme anchor.
- A first-board-radar trade without fresh public news is lower-confidence price discovery: it cannot be the only focus, its initial position is capped at 3%, and it must pass the same T+1 gate. Do not infer undisclosed information from unexplained strength.
- Reject any new-buy setup described as `只做日内`, `当天不对就走`, or dependent on a same-day stop. Those instructions are impossible for a new A-share position under T+1.
- Low position plus a positive story is not an expectation gap. If the strongest related theme is active but the stock still cannot show relative strength, treat that as market rejection until proven otherwise.
- The execution order must follow the executable ranking. A special-role candidate cannot be promoted above ranks 1-2 without explicit new auction/opening evidence and a written reason.
- Gap 0%-3%: normally comfortable when amount and theme confirm.
- Gap 3%-5%: wait for a hold/retest and second push.
- Gap 5%-7%: default priced-in/兑现 test in weak or rotating markets.
- Gap 7%-9%: no executable buy; use only as a theme anchor and wait for a later multi-session base.
- Gap at or near the price limit: never chase if it becomes tradable after opening. An opened limit-up or auction spike that loses the board is a sell-supply event, not a second chance.
- Small low open -1% to -3%: eligible only after quick repair with theme confirmation.
- Below -4%: default abandon unless a very hard catalyst receives immediate strong repair.

Ranks 1-2 must pass the big-move thesis, buyer/exit, and drawdown/cash-out gates. In a weak market, focus only one name or do not trade. When market breadth is below 30%, or synchronized Asian/overseas benchmarks signal a risk shock, default to no trade and leave `primary_pick` null before confirmation; only a confirmed counter-trend theme core may qualify, with initial position capped at 5%. Do not promote an unconfirmed low-position stock as a second focus. Do not change factor weights from a handful of outcomes; use the recommendation journal for forward validation.

## Required Chinese Output

Keep the answer compact and decision-oriented:

1. `数据口径、新题材雷达与市场总判断`: cutoff, auction/opening mode, top emerging themes with lifecycle/evidence, market regime, current message themes, and yesterday-line continuation/divergence/fade judgment.
2. `相关外围板块行情`: only finalist and holding themes, with benchmark, move, timestamp, impact, and affected codes.
3. `持仓早盘处置`: show ledger update time and actions, or state no confirmed holdings.
4. `候选排名（0-8只）`: for each give canonical code/name, role, selection model, direct evidence, underlying fact first-disclosure time, public availability at the decision cutoff, economic magnitude or narrative discontinuity, prior-thesis cooldown status, reference/current price, auction/opening condition, trigger status, buy trigger, abandon condition, suggested position, next buyer, T+1 survivability, and next-session sell discipline.
5. For rank 8 also give pattern date, pin low/recovery, range position, amount, MACD state, confirmation grade, and invalidation.
6. `第9只新题材专席`: output exactly one rigorously qualified stock with theme lifecycle and all six evidence gates, or `空缺（无合格新题材）`.
7. `首推审计`: show either one primary pick with latest-article time, first-disclosure time, what is genuinely new, materiality, strongest counterevidence, confirmation, and maximum position, or `今日无首推`.
8. `最终执行`: before auction show only `盘前优先观察` and keep executable focus empty; after auction/opening show only triggered focus names, key no-buy conditions, aggregate exposure, and `不交易` when confidence is insufficient.

## Mandatory Recommendation Journal

Before sending, record the exact final plan:

`venv/bin/python analysis/recommendation_journal.py record --mode morning --trade-date YYYY-MM-DD --input /tmp/morning_recommendation.json`

The input must include `decision_time`, `market_judgment`, `data_context`, `theme_radar`, `new_theme_candidate`, `overseas_sector_context`, `holding_actions`, zero to eight regular `candidates`, `risk_gate`, `primary_pick`, `provisional_focus_codes`, `focus_codes`, `no_trade`, and `response_summary`. `new_theme_candidate` is either the rigorously validated slot-9 object or null. `risk_gate` records market breadth, risk-off state, basis, and whether a confirmed counter-trend exception exists. `primary_pick` is either the separately audited first choice or null; its required audit includes latest article time, underlying fact first-disclosure time, oldest matching disclosure, at least 120 lookback days, freshness class, A materiality, original-source verification, genuine increment, economic magnitude, strongest counterevidence, confirmation, buyability, T+1 survival, reason for ranking first, and maximum position. Before auction, `focus_codes` is empty. Every provisional or executable focus candidate must also preserve execution-grade freshness, materiality, original-source verification, genuine increment, economic magnitude, market confirmation, buyability, and T+1 survivability. `theme_radar` preserves each leading term's lifecycle, first signal, overseas evidence, direct A-share anchors, next event, and invalidation. Preserve each candidate's canonical code/name, selection model, original source, fact first-disclosure time, public availability at the decision cutoff, economic magnitude or narrative discontinuity, failed-thesis cooldown status, actual evidence, time class, price, confirmation, trigger status, trigger, abandon condition, position, risks, next buyer, and sell discipline. Include first-board-radar evidence or pin/MACD evidence when those setups are present.

Never rewrite a sealed run after outcomes are known. A revision creates a new run. If journaling fails, do not issue executable focus; disclose the failure and return research observations only.
