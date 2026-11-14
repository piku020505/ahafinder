# Product memo: where Sona loses savers, and what to test next

**To:** Growth & Onboarding PMs | **From:** Product Analytics | **Data:** 100K installs, Jul-Sep 2026 (simulated)

## TL;DR
1. **Half of all KYC failures come from one segment.** Low-end Android phones are 22.1% of KYC starters but 50.1% of KYC failures, and 72% of their first failures are selfie/liveness checks. Their completion rate is 73.5%, against 94.0% for everyone else.
2. **We found an aha moment.** First-time buyers who either **enable AutoSave or make 3+ manual buys in week 1** keep coming back: 63.3% are active in the D30 window versus 20.1% of those who don't (3.1×). 63% of buyers already reach it, and it captures 84% of all retained users.
3. **Price alerts are a vanity feature.** They look like a +10.2 pp retention driver, but after controlling for other behaviour and user mix the effect shrinks to about +3.0 pp. Don't spend roadmap on them.

## Recommendation 1: fix KYC for low-end Android
- **Problem:** The selfie/liveness check fails on cheaper cameras. The app gives no fallback, so users give up after 1-2 attempts.
- **Proposal:** After one liveness failure, offer a fallback: Aadhaar offline XML plus a video-KYC slot, or retry with on-screen lighting guidance.
- **Size of prize (per quarter, at current volume):** closing half the gap gives about **+1,228 KYC completions, +787 first-time buyers (+2.5%) and +373 D30-retained savers**. Closing the full gap doubles that.
- **Metric:** KYC completion among low-end Android starters. **Guardrail:** KYC fraud and manual-review rate.

## Recommendation 2: test an AutoSave prompt after the first purchase
- **Why:** AutoSave is the strongest predictor of retention after adjusting for channel, city tier, device and other behaviours (+22.1 pp average marginal effect).
- **Caveat:** This is still observational. Motivated users both set up AutoSave *and* stay, so the true causal effect is smaller. **That is exactly why we test before we ship.**
- **Design:** A 50/50 split of first-time buyers, with an AutoSave set-up sheet shown on the purchase-success screen.
  - **Primary metric:** D30 retention.
  - **Secondary metric:** AutoSave adoption.
  - **Guardrails:** AutoSave cancellation within 14 days, mandate failure rate, refund requests.
- **Sample size:** to detect +2 pp on a 47.3% baseline (α = 0.05, power = 0.8), we need **9,800 buyers per arm, about 8 weeks** at current volume.

## Recommendation 3: make "3 buys in week 1" the onboarding goal
- Retention climbs fastest between 2 and 3 buys (+12.1 pp marginal gain), then flattens to about +5 pp per extra buy.
- **Ideas:** a 3-step "Gold streak" checklist, and a nudge on day 2 for users with exactly 1 buy.

## What I would NOT do
- Use "opened the app on 3+ days" as the aha moment. It predicts well (+22.2 pp adjusted), but it's an *outcome* of engagement rather than an action the product can drive, so optimising it leads to notification spam.
- Read the channel table as channel quality alone. Referral users retain better (55.8% vs 40.7% for paid social), partly because they arrive with more intent. Channel-mix changes need their own test.

## Validation
- The model was trained on the Jul-Aug cohorts and tested on the September cohort: **AUC 0.818**.
- The aha split held up out of time: 63.2% vs 19.7% D30 retention.
