# Pre-Board Discovery and False-Negative Audit

Use this reference when searching for a stock before its first obvious limit-up, or when reviewing why a later winner was absent from a morning/overnight list.

## Non-Negotiable Time Attribution

Classify every catalyst by its source timestamp relative to the price move:

1. `pre_move`: public before the move and eligible as a predictive catalyst.
2. `same_session`: public during the move; usable only after its timestamp.
3. `after_close`: eligible for the next trading session, not for explaining that day's first board.
4. `post_board`: explanatory evidence only; never backfill it into an earlier recommendation.

For company announcements, fetch the original detail by ID. A title/keyword match may discover a document but cannot establish catalyst hardness. Keep material risk events sticky for 15 calendar days unless a newer original announcement clearly resolves them.

## Coverage-Gap Check

The server index is the primary evidence base, but absence from the index is not proof that no public catalyst existed. Before finalizing leading candidates or auditing a missed winner, run a targeted source-gap check when network access is available:

1. exchange announcement and investor-interaction originals;
2. issuer website, newsroom, and official-account updates;
3. industry association, conference, policy-hearing, product-release, and scheduled-event notices;
4. reputable market reports that identify the timestamp and original source.

Record whether a finding was present in the server index, found only by supplemental search, or could not be verified. Never turn an unsourced forum claim into a hard catalyst.

Use two timestamps for scheduled events:

- `published_at`: when the notice first became public;
- `event_at`: when the conference, policy release, delivery, price adjustment, or industry action occurs.

A notice can be old but become decision-relevant again near `event_at`. Re-surface verified events at T-3, T-1, and T0 instead of discarding them merely because their publication date is outside today's headline window.

## Anchor-to-Beneficiary Reverse Map

When a market-recognized anchor reaches a first/second board or shows exceptional sector strength, reverse-map the industrial chain even if a target company has no fresh direct headline:

1. identify the exact product, capacity bottleneck, customer group, or policy node behind the anchor;
2. find all ordinary tradable A-share companies with pre-cutoff evidence of real capacity/business at that node;
3. separate capacity core, low-position substitute, loose concept, and denied exposure;
4. compare range position, trend repair, volume, auction/opening strength, and late-session acceptance;
5. keep an unconfirmed low-position peer in the scout lane and promote it only after live market confirmation.

This is not guilt-by-association. Product/capacity evidence must predate the decision. A strong peer plus a weak target tape is a watch signal, not a blind buy.

## Three Reusable Archetypes

### A. Deep-Base Latent Ignition

Typical shape:

- 10-day return roughly `-12%` to `+2%`.
- Position in the recent range is low or middle-low.
- Volume has contracted after a decline; the latest 2-3 sessions stop making smooth new lows.
- Close begins to reclaim MA3/MA5, but may still be below MA10.
- No fresh positive company catalyst is visible yet.

This is a **scout/watch** pattern, not an execution recommendation. Promote it only when a sector anchor, auction/opening confirmation, or real same-chain catalyst appears. A chart alone cannot distinguish ignition from a falling-knife continuation.

### B. Event Repricing After an Abnormal First Board

Typical sequence:

- The first board occurs before the hard announcement becomes public.
- A company-level message appears after close and can sustain the next day's narrative.
- The direct stock may become one-word/sealed and unbuyable.

Do not claim the after-close message predicted the first board. For the next session, use the direct stock as an anchor and search for buyable same-chain capacity cores or low-/middle-position substitutes. If the direct stock is already unavailable, recommendation quality depends on mapping the industrial chain correctly, not on chasing it.

### C. High-Volatility Emotion Reactivation

Typical shape:

- Multiple recent limit-ups and limit-downs or large alternating candles.
- High ATR, repeated abnormal-movement announcements, shareholder reduction, clarification, or weak fundamental disclosure.
- Price can still re-limit-up because recognition and emotion reactivate.

Classify it as an emotion/reactivation trade, never as quiet ignition or current hard logic. It may be a market flag, but it requires stricter auction/tape confirmation, smaller position, and a clearer T+1 exit path. A later limit-up does not invalidate an earlier risk-based rejection.

## Case Calibration: 2026-06

### 中化国际 600500

- On 2026-06-08 it closed down about 5.1%, below MA5, near the low of its 10-day range, with no visible company catalyst before the next open.
- On 2026-06-08, same-chain anchor 泰和新材 closed at its second limit-up while 中化国际 was still near the bottom. Older public information had already established 中化国际's para-aramid capacity and optical-cable use, so a reverse industrial-chain scan could have found it as a latent scout.
- The direct 8,000-ton high-utilization/TOP5-customer confirmation was timestamped 2026-06-09 15:50, after the first limit-up.
- The CNY 2.11B acquisition of 南通星辰 was disclosed after the 2026-06-10 close, after two boards had already occurred.
- Lesson: the first board was not a high-confidence overnight buy from the tape, but the stock was discoverable as a same-chain low-position scout before the board and as an event-repricing anchor afterward. The correct improvement is reverse mapping plus live confirmation, not using later announcements to manufacture foresight.

### 兰石重装 603169

- Before the 2026-06-16 board, its 10-day return was about -7.8%, it remained below MA10, and no positive company-level message appeared in the stored sources.
- A supplemental search found a 2026-06-15 issuer-official-account update: 20 core units for PetroChina Liaohe Petrochemical's 400,000-ton/year high-pressure lubricant hydrogenation project were completed and preparing for delivery. The stored announcement/news sources had missed this item.
- Its older nuclear-equipment contracts and third/fourth-generation nuclear-product exposure supplied the sector mapping, while the 2026-06-16 nuclear/energy-equipment move supplied market confirmation.
- Lesson: this was a genuine source-coverage miss plus deep-base ignition. Official issuer news must be checked for top latent scouts, but the weak pre-board tape still required auction/sector confirmation before execution.

### 莲花控股 600186

- Before the 2026-06-16 board, its 5-day/10-day returns were already about +15.5%/+23.2%, with ATR above 10% and prior limit-up/large-down volatility.
- Stored messages warned of abnormal trading, shareholder reduction, loss-making AI investment exposure, and underperforming server-rental activity.
- A supplemental search found that the 2026-06-16 High-Quality Token Service Seminar had been announced publicly on 2026-06-04/05. The event-day catalyst was knowable in advance, while the company's actual mapping came from its existing computing-power rental business.
- Lesson: this was scheduled-event reactivation with real but financially weak business exposure, not a quiet low-position hard-logic setup. An event calendar could have resurfaced it on T-1/T0, but risk disclosures still require conditional momentum treatment, smaller size, and strict tape confirmation.

## False-Negative Audit

When a missed stock later surges, assign exactly one primary reason:

1. `information_unavailable`: catalyst was not public before the decision.
2. `unbuyable`: signal existed but the stock was sealed or instantly unavailable.
3. `execution_rejected`: the idea existed but risk/reward, crowding, or tape failed.
4. `mapping_failure`: catalyst was public but the industry-chain beneficiary map missed it.
5. `ranking_failure`: candidate passed but was ranked too low.
6. `rule_gap`: reusable pre-move evidence existed and no current channel captured it.
7. `source_coverage_gap`: public evidence existed in an issuer/industry source outside the stored feed set.

`mapping_failure`, `ranking_failure`, `rule_gap`, and `source_coverage_gap` can justify a targeted change. Do not loosen execution rules for `information_unavailable` or for a high-risk stock that happened to rise.

## Ranking Integration

- Keep latent scouts separate from the seven executable candidates until confirmation.
- Use channel evidence as independent support/vetoes; raw vote count is not the final rank.
- Calibrate morning and overnight reliability separately.
- Require top-2 candidates to pass both a buyer/red-exit objective and a drawdown/cash-out-risk objective.
- Do not update channel weights from fewer than 40-60 forward decisions. Preserve sealed recommendations and evaluate out of sample.
