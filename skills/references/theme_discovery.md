# Emerging Theme Discovery

Use this reference before individual-stock ranking. The goal is to identify a new capital-market theme while it is moving from industry evidence to A-share recognition, without turning every overseas headline into speculative beneficiary mapping.

## Theme Before Stock

Run the theme process in this order:

1. discover fast-rising terms and causal phrases in recent news;
2. verify the physical/economic bottleneck through original or highly reliable sources;
3. locate direct A-share evidence and the first market-recognized anchors;
4. classify the theme lifecycle;
5. only then rank buyable stocks inside the verified theme.

Do not begin with a favorite stock and search backward for a fashionable label.

## Dynamic Novelty Radar

After the single server synchronization, run:

`venv/bin/python analysis/emerging_theme_radar.py --as-of DECISION_TIME --recent-hours 72 --baseline-days 21 --limit 12`

The radar compares the last 72 hours with a 21-day baseline. It surfaces suddenly accelerating material names, technical abbreviations, product bottlenecks, and industry terms. It is a discovery list, not a recommendation engine.

For each leading term inspect:

- recent frequency versus baseline;
- source diversity rather than duplicate article count;
- hard-cue density: shortage, price, backlog, export license, capacity, order, acquisition, joint venture;
- whether a primary foreign source still needs verification;
- whether a direct A-share filing/company exists;
- whether current market data confirms the theme.

A familiar broad word such as `AI`, `semiconductor`, or `robot` is not a new theme by itself. Prefer the newly scarce component or changed economic node inside the broad industry.

## Overseas Seed Signals

Overseas evidence is useful when it changes a concrete variable. Check these in priority order:

1. company earnings calls and investor materials: backlog, lead time, utilization, capacity expansion, customer demand, product mix;
2. government/customs/trade actions: export control, licensing delay, sanction, tariff, subsidy, standard;
3. physical prices and delivery data: spot price, contract price, inventory, delivery cycle, supply interruption;
4. major-customer product and capex changes: speed generation, architecture migration, order lock-up, long-term supply agreement;
5. directly relevant listed peers and commodities.

An overseas index rising or falling is a risk/confirmation input, not sufficient evidence for a new A-share theme. Require a causal chain:

`overseas fact → changed supply/demand/price/technology → exact domestic product node → direct public company evidence → A-share market recognition`

For a top-three emerging theme, make one batched external verification attempt when the local feed lacks the original foreign source. Preserve the original publication time and never use a later article as if it existed earlier.

## Theme Fact Card

Maintain one compact fact card per emerging theme:

- canonical theme name and aliases;
- first public signal and latest incremental signal;
- physical bottleneck or economic variable;
- overseas primary evidence and measured magnitude;
- domestic direct evidence;
- first A-share anchor and first-board date;
- breadth, amount, limit-up quality, and relative strength;
- lifecycle stage;
- direct companies, new-identity companies, emotion fronts, denied/loose mappings;
- next known event;
- invalidation and crowding/regulatory risks.

The theme card is rebuilt from current evidence; it is not a permanent concept list.

## Lifecycle

- `seed`: overseas/industry evidence exists, but no direct A-share filing or market anchor is confirmed. Research only.
- `emerging`: at least two independent evidence channels show the same bottleneck and A-share price/announcement evidence begins to appear. Highest discovery priority.
- `confirmed`: at least one direct anchor plus breadth/relative-strength confirmation; preferably two directly verified companies or a second independent market anchor. Candidate selection is allowed.
- `acceleration`: multiple boards, one-word leaders, rapid media expansion, and crowded replacement demand. Prefer buyable direct cores; do not chase sealed anchors.
- `overheat`: repeated one-word boards, denials/clarifications, abnormal-movement warnings, exchange monitoring, or loose-concept proliferation. No new high-position entries.
- `retreat`: anchors lose VWAP/support, breadth contracts, failed boards spread, and no fresh evidence arrives. Remove execution priority.

Do not call a theme `confirmed` from article count alone.

## Dedicated Ninth Slot

Morning output keeps the normal zero-to-eight candidate list unchanged and adds one optional `第9只新题材专席`. This slot is not a quota and cannot be filled by the best available weak idea.

Show a stock in slot 9 only when all conditions pass:

1. the radar finds a genuinely accelerating specific term rather than a broad industry label;
2. at least two independent positive evidence events exist after duplicate syndication is collapsed;
3. at least one original/primary source is verified;
4. overseas evidence changes a concrete supply, demand, price, technology, policy, backlog, capacity, or delivery variable;
5. an ordinary tradable A-share has direct company evidence, not reverse-inferred concept relevance;
6. a direct anchor or theme breadth provides market confirmation;
7. the selected stock is not a denial/loose mapping and is realistically buyable;
8. the setup passes the T+1 survivability gate.

If any condition fails, record `new_theme_candidate: null` and output `第9只：空缺（无合格新题材）`. Do not substitute an old theme, generic AI story, pure chart setup, or sealed limit-up.

An `emerging` theme may occupy slot 9 only with direct A-share and market confirmation. A `seed` remains in the research card and cannot occupy the slot.

## Direct A-Share Mapping

Theme discovery does not authorize free-form industrial-chain inference. A stock can enter the theme registry only through:

- a company/exchange filing that directly names the product/business;
- a reliable report quoting verifiable capacity, revenue, order, customer, production, or acquisition facts;
- current market recognition plus older public evidence that clearly predates the decision.

Classify each stock:

- `direct_current_business`;
- `new_identity_transaction`;
- `verified_future_capacity`;
- `emotion_front`;
- `denied_or_loose`.

Only the first three may become research candidates. `emotion_front` is a theme anchor; `denied_or_loose` is excluded.

## New-Business and Cross-Industry Radar

Within a confirmed/emerging theme, scan company filings for:

- acquisition of an operating business;
- joint venture or subsidiary formation;
- asset/team/patent/contract transfer;
- change of business scope or control;
- formal capacity project with funding, timetable, technology, and customers;
- strategic investment that grants operating control rather than a passive minority label.

Score the identity change separately from earnings:

- complete assets + team + intellectual property + contracts/clients: strong identity jump;
- controlled subsidiary/JV with credible technology and funded capacity: medium, pending execution;
- framework agreement, passive fund investment, business-scope registration, or generic cooperation: weak;
- company denial, zero staff/patents/revenue, or regulator challenge: risk downgrade.

The strongest identity jump still needs a buyable first/second-board window. A sealed board validates the theme but is not an executable recommendation.

## Case Calibration: InP, June 2026

The reusable sequence was:

1. overseas optical companies disclosed InP capacity/backlog pressure and AI data-center demand;
2. a direct A-share company announced a cross-industry InP project and became the first anchor;
3. export licensing and supply concentration turned the material into a geopolitical/AI bottleneck story;
4. domestic news and research repeated measurable shortage/capacity evidence;
5. another small-cap company acquired a complete InP operating business and received a new market identity.

The theme should therefore have been in the `emerging` registry before the later company's acquisition announcement. The later company was not predictable from undisclosed information, but the theme itself was discoverable and deserved priority over stale individual-company stories.

## Audit

For every missed large winner, first ask:

1. Was the theme discoverable before the move?
2. Was the company directly mapped before the move?
3. Was the stock buyable when confirmation appeared?

Use one primary failure label:

- `theme_discovery_failure`;
- `foreign_source_gap`;
- `direct_mapping_failure`;
- `identity_change_missed`;
- `market_confirmation_missed`;
- `unbuyable`;
- `information_unavailable`;
- `execution_rejected`.

Only the first five justify changing discovery logic. Do not loosen risk controls for information that was unavailable or a stock that was never realistically buyable.
