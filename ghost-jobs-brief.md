# JobTruth: Team Brief

IBM Z Datathon 2026 (24 hours) · Last updated 2026-10-15

## What we're building

**JobTruth scores how likely a job posting is to be fake, then confirms whether the employer actually hires, using confidential state hiring records that never leave an encrypted LinuxONE enclave.** Track: Theme 2, AI Secured (with real-time scoring as a Theme 1 feature).

Three deliverables:

1. **Ghost-job scorer (core, fully built):** paste any job posting, or stream new ones in, and get a 0–100% ghost-job likelihood with plain-language reasons. Runs on the Telum on-chip AI accelerator.
2. **Hiring-verification enclave:** inside LinuxONE Secure Execution, match postings against synthetic New Hire Directory and wage records. The only output is an employer-level "hiring follow-through score" published with differential privacy; raw hire or wage data never comes out.
3. **Stretch output (only if the core works by hour 14):** either a *ghost-adjusted job openings index* for NY, or a *subsidy jobs-promise check* showing whether companies that got tax breaks really hired.

Scope: postings from New York State employers. Roadmap only (not built): early warning for official job-estimate revisions.

## The problem

Ghost jobs, postings with no real intent to hire, waste job seekers' time and make the job market look stronger than it is. The data that could prove which jobs are real exists, but it's confidential.

- **Job seekers:** hours lost applying to postings that were never going to be filled. The worst-hit are unemployed workers, new grads and career changers.
- **Unemployment claimants:** NY claimants must log job applications each week to keep their benefits. Ghost postings make the state require wasted effort.
- **Policymakers:** job-openings statistics (JOLTS) may count ghost postings, so labor demand looks higher than it is. Official job numbers get large later revisions too (about −818,000 jobs in the 2024 benchmark revision).
- **Taxpayers:** companies promise jobs in exchange for tax breaks, and checking whether they hired depends largely on their own reporting.
- **Why now:** Ontario now requires postings to disclose whether a vacancy exists, and several US states have proposed ghost-job bills.

All statistics are approximate and from memory. Check each one against its source before it goes on a slide.

## How it works

Public postings get scored in real time; confidential hiring records stay inside the enclave and confirm or correct those scores.

```
Public postings ──┐         ┌─ LinuxONE Secure Execution enclave ─┐──▶ Job seekers:   "Is this posting real?"
WARN notices ─────┼────────▶│ 1 Ghost-job scorer (Telum)          │──▶ NY Dept of Labor: flag ghost postings
New-hire reports ─┤ (enc.)  │ 2 Posting ↔ hire matching           │──▶ Policymakers / taxpayers:
UI wage records ──┘         │ 3 Follow-through score + DP release │      ghost-adjusted index or subsidy check
                            └──────── keys in HSM ────────────────┘
```

1. **Ghost-job scorer:** features from public data (how often a posting is reposted, how long it stays open, how vague the description is, salary-range width, recent layoff notices from the same employer) plus LLM analysis of the posting text. Output: a score with the top reasons.
2. **Posting-to-hire matching:** inside the enclave, link each employer's postings to new-hire reports by employer ID, job title or occupation code, and date window. Did a hire follow within about 60 days?
3. **Follow-through score:** per employer, the share of postings followed by a real hire, released with differential privacy so no individual worker or hire can be identified.
4. **Feedback loop:** use the enclave's verified outcomes to recalibrate the public scorer, so the scorer learns from confidential data without ever exposing it.

## Why IBM Z / LinuxONE

**Pitch line:** *"Whether a job is real can only be proven with hiring records that legally can't leave the state, so we bring the AI to the data, inside a LinuxONE enclave nobody can see into."*

| Z feature | How JobTruth uses it |
| --- | --- |
| Secure Execution enclave | Confidential new-hire and wage records are analyzed without admins, IBM or other agencies seeing them |
| Telum on-chip AI | Scores every new posting as it arrives; we report postings scored per second |
| HSM / pervasive encryption | The labor department keeps control of its own keys; data is encrypted at rest and in use |
| Data gravity | State wage and benefits systems already run on mainframes; the AI moves to the data |
| Scale and uptime | Benchmark throughput, then project it: "every US posting, scored daily" |

Make the enclave visible in the demo: an "outside analyst" tries to query raw hire records and is denied.

## Data plan

Postings are real public data; hiring records are synthetic, and the pitch says so plainly.

| Dataset | Source | Real or synthetic | Used for |
| --- | --- | --- | --- |
| Job postings | Public Kaggle LinkedIn postings dataset, filtered to NY employers | Real | Scorer features, demo |
| Layoff notices | NY State WARN notices (public) | Real | Scorer feature |
| New-hire reports | Generated per employer with a hidden "true" hire rate, including some ghost-posting employers | Synthetic | Enclave matching |
| Quarterly wage records | Generated headcount by employer and quarter, consistent with the new-hire data | Synthetic | Follow-through score, subsidy check |
| Subsidy promises (if we pick it) | Published NY incentive program awards | Real if available, else synthetic | Jobs-promise check |

- **Validate the scorer without synthetic data:** use real signals as weak labels (reposted 3+ times, open 60+ days, recent layoff notice) so the results aren't circular.
- **Agree on schemas before the event:** employer ID, job title or occupation code, posting date and close date, hire date. That lets the ML and data owners work in parallel.
- **Open question:** is the Kaggle dataset recent and large enough for NY? Check now and have a backup source ready.

## Pitch framing

Lead with people harmed, then the confidential-data problem, then the enclave. Don't claim the government fakes numbers: say the data that would make the numbers accurate exists but can't be used safely or in time.

| Likely judge question | Our answer |
| --- | --- |
| "Couldn't this run on a laptop?" | The scorer could. Proof can't: it needs confidential hiring records that legally must stay inside state systems. |
| "Isn't your ground truth made up?" | The enclave data is synthetic by necessity. The scorer is validated separately on real public signals. |
| "Who would deploy this?" | NY State Department of Labor, for its own job bank and to protect claimants who must log applications. |
| "Is it fair to employers?" | Scores are probabilities with reasons, not accusations, and employers can see and contest their own scores. |
| "Why is this AI for Good?" | It protects unemployed workers' time and makes labor statistics more honest. |

## Team plan

| Role | Owns |
| --- | --- |
| ML lead (grad) | Ghost-job scorer: features, model, LLM text analysis, explanations |
| Data lead | Postings and WARN pipeline, synthetic hiring records, matching, differential privacy, stretch output |
| Platform lead (CE/systems) | LinuxONE setup, Secure Execution enclave, keys, compiling the model for Telum, throughput benchmark |
| Product and pitch lead | Demo UI, "access denied" moment, deck, video, owns the story from hour one |

**Before the event (no code):**

- [ ] Confirm the rules: theme selection, separate track prizes, what prep is allowed
- [ ] Find out exactly what LinuxONE access includes (Secure Execution? Telum tooling? watsonx or a local LLM?)
- [ ] Check that our Python libraries install on s390x
- [ ] Download the postings dataset and NY WARN notices; check coverage
- [ ] Agree on data schemas on paper
- [ ] Verify every statistic for the slides and save sources
- [ ] Optional: get a quote from a job seeker, career counselor or workforce agency

**24-hour schedule** (code freeze at hour 20; sleep in two shifts of about 3 hours, never both owners of a dependency at once):

| Hours | Work |
| --- | --- |
| 0–2 | Everyone on LinuxONE; repo, environment and data loaded; schemas confirmed |
| 2–8 | In parallel: scorer v1 with weak labels (ML) · synthetic hiring records and matching (Data) · enclave and keys (Platform) · demo UI skeleton and deck outline (Pitch) |
| 8–12 | Integrate: scorer and matching running inside the enclave; follow-through score with differential privacy |
| 12–16 | Model on Telum and throughput benchmark; "access denied" demo; stretch output only if on track |
| 16–20 | Polish demo, fix bugs, record backup demo video. Code freeze at hour 20 |
| 20–24 | Final deck and video, two full rehearsals, submit with time to spare |

**Demo (about 90 seconds, and record a backup video in case live fails):** paste a real NY posting and get "82% likely ghost" with reasons → open that employer's follow-through score from the enclave → an outside analyst tries to read raw hire records and is denied → close on the throughput number and the people this protects.
