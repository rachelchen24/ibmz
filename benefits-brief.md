# Unclaimed: Team Brief (backup idea)

IBM Z Datathon 2026 (24 hours) · Last updated 2026-10-15

## What we're building

**Unclaimed finds New Yorkers who qualify for benefits they never claimed (EITC, SNAP, Medicaid) by matching records across tax, SNAP and Medicaid agencies inside an encrypted LinuxONE enclave. No agency ever sees another agency's data; the only output is a plain-language notice to the resident.** Track: Theme 2, AI Secured.

Three deliverables:

1. **Confidential matching and eligibility pipeline (core, fully built):** three synthetic agency datasets go into a LinuxONE Secure Execution enclave. Inside it: fuzzy record matching across agencies, eligibility checks with PolicyEngine-US, and a ranked list of likely-eligible households with confidence scores.
2. **Outreach notice generator:** for each flagged household, a plain-language notice ("you may qualify for $X, here's how to claim") in the resident's language, generated inside the enclave.
3. **Stretch output (only if the core works by hour 14):** a borough-level dashboard of unclaimed dollars for policymakers, released with differential privacy.

Scope: New York City (5 boroughs) under NY State rules. The state is a config setting, so adding another state is a configuration change, not a rebuild.

## The problem

Billions of dollars in benefits go unclaimed every year, mostly by low-income families. The data to find them already exists, but it's split across agencies that can't legally or practically pool it.

- **Scale:** about 1 in 5 people eligible for the EITC don't claim it; SNAP and Medicaid have similar gaps.
- **NYC stacks credits:** federal EITC + Empire State EITC + NYC's own city EITC. One missed tax filing loses all three.
- **Three levels of government:** IRS and NY State tax, NY State of Health (Medicaid), and NYC HRA (SNAP, Medicaid locally) each hold one piece.
- **Language barrier:** NYC Local Law 30 requires city services in about 10 languages; many eligible families are missed partly because outreach isn't in their language.
- **Precedent:** "direct certification" already enrolls kids in free school meals using SNAP and Medicaid data. We generalize a policy that is proven to work.

All statistics are approximate and from memory. Check each one against its source before it goes on a slide.

## How it works

Each agency sends encrypted records into one enclave; matching and AI run inside it; only notices and privacy-protected statistics come out.

```
Tax (IRS + NY DTF) ──┐               ┌─ LinuxONE Secure Execution enclave ─────┐
SNAP (NYC HRA) ──────┼─ encrypted ──▶│ 1 Entity resolution  2 Eligibility      │──▶ Outreach notices
Medicaid (NYSOH) ────┘   feeds       │ 3 Prioritization     4 Notice generator │──▶ DP borough stats
                                     │ 5 Policy view        (keys held in HSM) │
                                     └─────────────────────────────────────────┘
```

1. **Entity resolution:** fuzzy-match people across agencies when names, addresses and household composition don't line up exactly. This is the main ML problem.
2. **Eligibility engine:** PolicyEngine-US for the legal rules, plus ML to estimate fields one agency doesn't hold (such as household income). Each match gets a confidence score.
3. **Prioritization:** rank cases by expected dollars × likelihood the person claims.
4. **Notice generator:** an LLM inside the enclave writes a plain-language, multilingual notice at a 6th-grade reading level with exact next steps.
5. **Policy view:** differentially private stats, e.g. "the Bronx is leaving $X of EITC unclaimed."

## Why IBM Z / LinuxONE

**Pitch line:** *"Agencies don't have to trust each other. They only have to trust the enclave."*

| Z feature | How Unclaimed uses it |
| --- | --- |
| Secure Execution enclave | Agencies' records are matched without any agency, admin or IBM seeing them; this is what makes data sharing legally plausible |
| Data gravity | State benefits and tax systems often run on mainframes; the AI moves to the data |
| Telum on-chip AI | Screens every resident in a nightly batch, or instantly when someone applies for any one program ("no wrong door") |
| HSM / pervasive encryption | Each agency keeps control of its own keys |
| Scale and uptime | Benchmark throughput, then project it: "every US household screened overnight" |

Make the enclave visible in the demo: an "agency admin" tries to query another agency's raw records and is denied.

## Data plan

Everything is synthetic but built from real census microdata, and the pitch says so plainly.

| Dataset | Source | Used for |
| --- | --- | --- |
| Synthetic NYC population | ACS PUMS microdata for NYC (about 80k person records) | Realistic households, incomes, languages |
| Eligibility rules | PolicyEngine-US (open source); check that it models the NYC EITC and NYC income tax, else add the formula | True eligibility per household |
| "Who didn't claim" | Published EITC and SNAP participation rates | Deciding which eligible households are missing |
| Three agency views | Split from the population, each agency holding only its own fields, with deliberately messy names and addresses | Entity resolution, enclave demo |

- **Agree on schemas before the event:** the exact fields each agency holds, so the ML and data owners can work in parallel.

## Pitch framing and responsible AI

Lead with one family, then the data-sharing barrier, then the enclave.

| Likely judge question | Our answer |
| --- | --- |
| "Doesn't ACCESS NYC already do this?" | ACCESS NYC waits for people to come to it. We reach the people who never will. |
| "Isn't this surveillance?" | Purpose limitation: the enclave can only run outreach, never enforcement or fraud hunting. |
| "What if you're wrong?" | Notices say "you may qualify, here's how to check." We never auto-enroll, because a wrong enrollment can lead to clawbacks. |
| "Is it fair?" | We audit match and eligibility rates across language, borough and immigrant households, the groups most often missed. |
| "Why IBM Z?" | Government data can't go to a cloud AI, so the AI goes to the data, inside an enclave nobody can see into. |

## Team plan

| Role | Owns |
| --- | --- |
| ML lead (grad) | Entity resolution, eligibility inference, confidence scores |
| Data lead | Synthetic population from PUMS, agency splits, PolicyEngine integration, DP stats, fairness audit |
| Platform lead (CE/systems) | LinuxONE setup, Secure Execution enclave, keys, model on Telum, throughput benchmark |
| Product and pitch lead | Dashboard, notice generator, "access denied" moment, deck, video, owns the story from hour one |

**Before the event (no code):**

- [ ] Confirm the rules: theme selection, separate track prizes, what prep is allowed
- [ ] Find out exactly what LinuxONE access includes (Secure Execution? Telum tooling? watsonx or a local LLM?)
- [ ] Check that PolicyEngine-US and our matching library install on s390x
- [ ] Download NYC ACS PUMS data
- [ ] Agree on the three agency schemas on paper
- [ ] Verify every statistic for the slides and save sources
- [ ] Optional: get a quote from a VITA free tax-prep site or a benefits nonprofit

**24-hour schedule** (code freeze at hour 20; sleep in two shifts of about 3 hours, never both owners of a dependency at once):

| Hours | Work |
| --- | --- |
| 0–2 | Everyone on LinuxONE; repo, environment and PUMS data loaded; schemas confirmed |
| 2–8 | In parallel: synthetic population and agency splits, PolicyEngine running (Data) · entity resolution v1 (ML) · enclave and keys (Platform) · dashboard skeleton and deck outline (Pitch) |
| 8–12 | Integrate: matching and eligibility running inside the enclave; ranked household list |
| 12–16 | Notice generator; model on Telum and throughput benchmark; "access denied" demo; stretch dashboard only if on track |
| 16–20 | Polish demo, fix bugs, record backup demo video. Code freeze at hour 20 |
| 20–24 | Final deck and video, two full rehearsals, submit with time to spare |

**Demo (about 90 seconds, and record a backup video in case live fails):** dashboard shows "$X million unclaimed across N NYC households" → click one Bronx household to see why it was flagged and its notice in Spanish → an agency admin tries to read another agency's raw records and is denied → close on the throughput number and the families this reaches.
