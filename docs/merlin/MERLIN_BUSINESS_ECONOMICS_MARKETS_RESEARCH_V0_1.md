# Merlin Business, Economics & Markets Research v0.1

**Status:** architecture and research protocol. This document does not authorize brokerage activity, investment recommendations, or live order placement.

## Mission
Give Merlin a rigorous, continually updated body of knowledge spanning business fundamentals, finance, economics, market structure and investable instruments. Build explanations from observed constraints and mechanisms, not from the prestige of a textbook, institution, influencer or prevailing school of thought.

Merlin must distinguish observed facts, accounting identities, definitions, assumptions, causal claims, forecasts and value judgments; market price, fundamental value estimates, liquidity, funding cost and transaction cost; evidence of demand, willingness to pay and realized revenue; issuer claims, analyst interpretation and independently verified facts.

## 1. First-principles economics
Start with agents, objectives, constraints, resources, production technologies, property and control rights, institutions, enforcement, information, uncertainty, time and geography. Derive models from these primitives and make assumptions visible.

The idea-space should cover:
1. scarcity, choice, opportunity cost and marginal trade-offs;
2. production functions, productivity, capital, labor, energy and materials;
3. specialization, coordination, transaction costs and firm boundaries;
4. exchange, matching, bargaining, auctions, market design and price discovery;
5. money, credit, collateral, maturity transformation and payment/settlement;
6. accounting identities, balance sheets, flows, stocks and sectoral consistency;
7. expectations, information asymmetry, search, signaling and principal-agent problems;
8. competition, market power, entry, exit, rents and network effects;
9. externalities, public goods, commons, regulation and institutional design;
10. uncertainty, risk, insurance, options, liquidity and systemic feedback;
11. distribution, incidence, bargaining power, household constraints and political economy;
12. spatial economics, housing, infrastructure, demographics and local demand.

Derive mathematics rather than importing equations as unquestioned truths: constrained optimization from explicit objectives and feasible sets; duality and shadow prices from constraint changes; accounting identities from consistent double-entry records and stock-flow accounting; equilibrium as a possible consistency condition, not a guarantee that markets clear instantly or fairly; game theory from strategic interdependence and specified information; stochastic processes from explicit uncertainty assumptions; econometrics and causal inference from identification assumptions, not correlation alone; network flow and matching from actual routing, capacity and allocation mechanisms.

For every model, store primitives, assumptions, equations, units, domain, equilibrium concept if any, testable implications, known failure conditions, counterexamples, empirical sources and competing explanations. Compare classical, neoclassical, Keynesian, post-Keynesian, Austrian, institutional, Marxian, behavioral, ecological, complexity, evolutionary and other relevant traditions as competing or complementary model families. Do not treat any school as a monolith or accept a claim because it belongs to a named school.

## 2. Ideonomy: enumerate the idea space
Build a typed graph, not a flat glossary. Nodes include primitive, definition, mechanism, institution, model, equation, empirical regularity, hypothesis, measurement, dataset, historical episode, counterexample and unresolved question. Edges include derives_from, assumes, predicts, measured_by, contradicted_by, equivalent_under, applies_to, historically_preceded_by and tested_on.

Use morphological analysis to enumerate combinations across actors × constraints × institutions × information × time × geography × market design. Deduplicate equivalent ideas while retaining genuinely different assumptions. Track unexplored combinations and uncertainty. Novelty is a candidate label, never proof of truth.

Every claim has a status: candidate, source_checked, data_reproduced, counterexample_checked, empirically_supported, formally_derived, contradicted or unresolved. Keep provenance and revisions.

## 3. Business and finance curriculum (MBA-equivalent knowledge map)
The goal is capability, not a credential. Cover financial accounting and statement reconstruction; managerial accounting, cost behavior, budgeting and variance analysis; corporate finance, capital structure, capital budgeting, valuation and cost of capital; strategy, competitive advantage, industry structure and business models; marketing, customer discovery, pricing, distribution and retention; operations, supply chains, capacity, inventory and quality; organizational behavior, incentives, governance, leadership and negotiation; entrepreneurship, product-market fit, sales economics and financing; managerial economics, statistics, econometrics and decision science; business law, contracts, compliance, tax, ethics and fiduciary duties; risk management, treasury, working capital, liquidity and crisis planning.

Require applied cases: reconstruct a company's economics from filings; build a three-statement model; stress-test a debt schedule; analyze customer acquisition and retention; map competitors and suppliers; evaluate a capital project; write an investment memo with bear/base/bull cases and a falsification plan. Use actual historical filings and preserve the information set available at the time.

## 4. Source integrity and persuasion-risk scoring
Do not use a single opaque credibility score. Keep four separate assessments.

**Authority and provenance (0–100):** original issuer, statutory/official source, named author, traceable methodology, stable identifier, source document and verifiable publication time.

**Data quality (0–100):** completeness, definitions, units, revision history, sampling, coverage, known bias, missingness and reproducibility.

**Promotional-pressure indicator (0–100):** commercial relationship or affiliate compensation, issuer/position exposure, sponsored placement, urgency/scarcity language, guaranteed-return claims, unverifiable performance, selective backtests, referral incentives and absence of independent corroboration. This is a risk flag about incentives and persuasion tactics, not a finding of dishonesty or intent. Explain each component and show unknowns as unknown, not zero.

**Claim support (0–100):** independent corroboration, primary evidence, reproducible calculation, out-of-sample evidence and consistency with contrary evidence. A high authority score does not make every claim true; an official source can be wrong or incomplete.

Never let promotional content silently enter the evidence base as neutral fact. Preserve original text, extraction, normalized claim, source hash, retrieval time, source author, commercial disclosures and model interpretation. Search for disconfirming evidence.

## 5. Public local-demand intelligence
County and municipal public records can reveal projects, procurement intent, zoning changes, capital plans, service constraints and local spending priorities before they appear in annual statistics. They are **leading clues, not proof of market demand**.

Ingest agendas, minutes, staff reports, adopted budgets, capital improvement plans, procurement notices, bid tabs, awarded contracts, permits, planning cases, utility plans and public dashboards. Begin with a pilot for Pima and Maricopa counties, but keep the source adapter generic.

Extract structured events: jurisdiction, meeting date, publication date, agenda item, project/entity, location, industry/NAICS hypothesis, proposed amount, approved amount, funding source, procurement stage, expected timing, vote/status, named suppliers, cancellation/amendment and source-page citations.

Deduplicate repeated agenda items and revisions. Distinguish proposal, discussion, authorization, appropriation, solicitation, award, obligation, invoice and completed delivery. Map records to geography and industry only with confidence and explanation. Validate minutes against later procurement awards, permits, budgets, contracts, Census and BEA data. Account for reporting lags, political framing, nonbinding motions, missing minutes and selection bias. Do not infer private purchasing intent from public deliberation.

## 6. Authoritative source families
Initial source registry is docs/research/merlin-economic-data-source-registry.v1.json. Prioritize primary records: SEC EDGAR filings and XBRL company facts for issuer fundamentals; BEA GDP, industry accounts, input-output tables and regional accounts; BLS labor, wages, prices and productivity; FRED and ALFRED for macro series and historical data vintages; Federal Reserve Financial Accounts (Z.1) for sector balance sheets and flows; Treasury yield curves, auction and debt data; CFTC Commitments of Traders for reported futures positioning; FINRA TRACE datasets for eligible fixed-income transaction aggregates; OCC derivatives reports and bank call-report-derived statistics; Census ACS, County Business Patterns, permits and population estimates; USAspending for federal awards and obligations; state, county, municipal, school-district and utility primary records.

Record the data owner's definition and release calendar. Do not confuse a convenient aggregator with the original data producer. Respect API limits, terms, privacy and licensing; free access does not imply unrestricted redistribution.

## 7. Investable-market coverage
Build a read-only instrument ontology and market calendar across listed equities, ADRs, ETFs, ETNs, closed-end funds and REITs; sovereign, municipal, agency, corporate and securitized fixed income; cash and money-market instruments; listed options, futures and exchange-traded derivatives; FX and commodity markets; private equity, private credit, venture and real assets where data coverage is sparse; and digital assets where legally accessible and provenance is adequate.

For each instrument capture venue, identifier, contract terms, currency, trading calendar, liquidity, bid/ask or proxy, volume, settlement, fees, leverage, margin, borrow/short constraints, corporate actions, tax/regulatory treatment and data entitlement. Mark inaccessible, delayed, stale or incomplete markets. Do not imply all assets are equally liquid or directly investable by every user.

## 8. Daily research scan and opportunity triage
A daily scan should produce a research queue, not automatic trades:
1. verify market calendar, data freshness and source health;
2. ingest corporate filings, earnings releases, macro releases, rates, market structure and relevant local-demand events;
3. update fundamentals and valuation ranges using point-in-time data;
4. detect changes in estimates, liquidity, leverage, credit conditions, positioning and catalysts;
5. compare each hypothesis against a benchmark and plausible alternatives;
6. calculate scenario ranges, expected value under explicit assumptions, downside, drawdown, liquidity and transaction-cost sensitivity;
7. produce an evidence-backed memo with bear/base/bull cases, what would falsify the thesis, missing data and confidence;
8. retain a dated snapshot so future tests do not use revised data unknowable at the time.

Rank by a transparent multi-factor dashboard rather than one magical alpha score: evidence quality, valuation dispersion, catalyst strength, balance-sheet resilience, liquidity, downside severity, model uncertainty and portfolio correlation. Separate statistical signal from investment suitability. A score is triage, not a guarantee of excess returns.

## 9. Research mathematics and evaluation
Use accounting identities, discounted cash-flow analysis, multiples with comparability checks, duration/convexity, credit and default models, option pricing, term-structure models, portfolio optimization, factor models, Bayesian updating, causal inference, time-series analysis, survival analysis and network analysis where assumptions fit. Maintain a model card with equations, units, estimation window, parameters, calibration, failure modes and validation.

Backtests must address look-ahead bias, survivorship and delisting bias, revised macro data, corporate actions, multiple testing, regime shifts, transaction costs, taxes, slippage, liquidity and capacity. Use walk-forward and genuinely held-out periods. Compare to simple baselines. Publish negative results and failed hypotheses.

## 10. Governance boundary
Initial implementation is research-only and read-only. No brokerage credentials, order submission, account transfers, automated recommendations personalized to a person's financial circumstances, or trade execution. Any future market connection requires a separately reviewed adapter, explicit user approval, documented permissions, independent risk limits and a kill switch. Never store brokerage secrets in source control or research artifacts.

## First implementation milestones
1. Validate source registry and event/claim schemas.
2. Implement provenance ledger and promotional-pressure scoring with tests.
3. Build filing and macro-data ingestion with point-in-time snapshots.
4. Add local public-record ingestion and event extraction with human verification.
5. Build fundamentals and market instrument ontology.
6. Create daily read-only research queue and reproducible memo.
7. Add economics idea graph, model cards and counterexample workflow.
8. Add case-based MBA-equivalent learning paths and demonstrated-skill assessment.

Production readiness requires real source fetches, retained logs, reproducible fixtures, stale-data behavior, rate-limit handling, security review and independent validation. This specification alone is not a functioning market scanner.
