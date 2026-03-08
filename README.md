# BetaBridge

> Beta-to-paid conversion tracker for SaaS founders. Track every beta user journey — signup source, activation events, NPS score. Surface which cohorts convert and why.

## Problem

Most SaaS founders have 50-200 beta users but no visibility into why 97% never pay. They send manual check-ins, guess at activation blockers, and have no data on which acquisition channels produce paying customers. The result: months of free beta with nothing to show.

## Market

- **TAM**: $6.8B — Product analytics and user behaviour platforms (2025)
- **SAM**: ~$900M — Early-stage SaaS product analytics (250K+ early-stage SaaS globally)
- **CAGR**: 18.4% through 2030 (PLG motion adoption, self-serve SaaS growth)
- **Trend**: 68% of early SaaS founders cite "don't know why users don't convert" as top challenge (FirstRound Capital Survey, 2025)

## Competitors

| Tool | Strength | Weakness |
|------|----------|----------|
| Mixpanel | Deep event analytics | Expensive, complex setup |
| Amplitude | Enterprise-grade funnels | Overkill for early stage |
| PostHog | Open-source, full suite | Self-host complexity |
| June.so | Simple SaaS metrics | Segment required, $99+/mo |
| Spreadsheets | Free | No automation, no correlation |

## Differentiation

- **Beta-specific workflow** — not a generic analytics tool; built for the 0→$1K MRR journey
- **NPS + events correlation** — automatically surfaces what high-NPS users do differently
- **Source attribution** — see which channels (PH, HN, Twitter) actually produce paying customers

## Economics

- **Pricing**: Free (up to 50 users), $29/mo (500 users), $79/mo (unlimited)
- **Target**: Solo founders and early-stage SaaS teams in beta phase
- **MRR at scale**: 2,500 teams × $29 = **$72.5K MRR / $870K ARR**
- **CAC**: ~$30 (dev communities, Indie Hackers), LTV: $348 (12mo avg) → LTV/CAC = 11.6×

## Scoring

| Criterion | Score |
|-----------|-------|
| Pain severity | 4/5 |
| Market size | 3/5 |
| Technical barrier | 3/5 |
| Competitive gap | 3/5 |
| Monetisation clarity | 4/5 |
| **Total** | **3.4/5** |

## API Endpoints

```
POST /users              — register beta user (idempotent by email)
GET  /users?status=      — list users (beta | converted | churned)
POST /events             — track activation/usage event
POST /nps                — record NPS score (0-10)
POST /convert            — mark user as paid (plan + MRR)
GET  /funnel             — conversion rate, MRR from beta, avg events, top sources
```

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
# Docs at http://localhost:8000/docs
```
