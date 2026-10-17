# RealRole: Start Here

Read this first. It explains what we're building, which files to read, and what to do before the event. It's written for **teammates who weren't part of the planning** and for **their AI coding agents**.

## The project in one paragraph

We're entering the **IBM Z Datathon 2026** (October 17–18, 2026), competing **in person at the New York hub**, in **Theme 2: AI Secured (Innovation Without Exposure)**. We're building **RealRole**, which detects **ghost jobs**: job postings from real employers that never lead to a hire. RealRole has a Chrome extension that shows a "ghost-likely" score on any job posting, a web app where you can paste a listing, an application tracker with community reports, and a policy dashboard. Behind them, an AI system on IBM's **LinuxONE** mainframe scores postings and checks whether employers actually hire, using confidential hiring records (synthetic, for the competition) that never leave an encrypted, isolated zone. Judges score four things equally: value to the community, originality, technical use of LinuxONE and AI, and the quality of our 3-minute demo video.

## The team

| Workstream | Who | Builds |
|---|---|---|
| A: AI/ML | *(fill in)* | The models: scorer, time-to-hire model, Granite text features, evaluation |
| B: Data and confidential zone | *(fill in)* | Synthetic hiring records, the confidential zone, real-data validation, policy dashboard |
| C: Platform | **Michael** (owns the LinuxONE server) | Server setup, API, database, containers, security, benchmarks |
| D: Product | *(fill in)* | Chrome extension, web app, application tracker, employer page; leads the pitch video |

Each person works with their own AI coding agent, on their own part of the code, at the same time.

## Files, and what to read

| File | What it is | Who reads it |
|---|---|---|
| **START-HERE.md** | This file | Everyone, first |
| **[realrole-brief.md](realrole-brief.md)** | The project spec: what we're building, official rules and judging, how it works, data, team plan, video plan | Everyone: read it all (about 15 minutes) |
| **[realrole-build-plan.md](realrole-build-plan.md)** | Task briefs for each workstream, the shared contracts (data formats, API, ports), and how we work in parallel | Everyone: "How to use this plan," Part 1, Part 2, and **your own workstream's tasks** in Part 4 |
| [realrole-research.md](realrole-research.md) | Background research: datasets, real government record layouts, model ideas, LinuxONE notes, statistics | Reference: look things up as needed |
| [data/README.md](data/README.md) | What's in each downloaded dataset, coverage, and known gaps | Workstreams A and B; reference for others |
| benefits-brief.md | An earlier backup idea we're **not** building | Nobody needs it |

The `.docx` files are Word copies of the same documents.

## Rules everyone must follow

1. **No code before the event starts.** The official rules require all code to be written during the event. Reading, planning and downloading data are fine.
2. **Both IBM labs are mandatory before we build:** "Predictive AI Hybrid AI scenarios (multi-model)" and "Predictive AI + Generative AI." They're the first thing we do at kickoff.
3. **Everything runs on the LinuxONE Community Cloud** (Michael's server), and we take **screenshots** as evidence for judges.
4. **List every open-source library you use** (with a link) in `docs/open-source.md`. The rules require it.
5. **No political messaging** in anything we produce; talk about job seekers and data accuracy.
6. **No real personal data.** Hiring records are synthetic; NYC payroll name columns are never loaded.

## How we'll use AI agents

- There are **no ready-made prompts**. The build plan gives each task's goal, inputs and outputs, details, open questions and "done when."
- For each task: **explore it with your agent** (look at the real data, discuss approaches, settle the open questions) → have the agent **draft a master prompt** → **edit it yourself** → send it → review the result → save the final prompt in `docs/prompts/`.
- Agents only edit their own workstream's folders and follow the shared contracts. Anything that changes a contract gets agreed by the whole team first.
- A person reviews every pull request before it merges.

## Before tomorrow: checklist

**Everyone**
- [ ] Read this file, the brief, and your part of the build plan
- [ ] Make sure your AI coding agent is installed, logged in and working on your laptop
- [ ] Install **Python 3.11+** and **Git** on your laptop; have a **GitHub** account
- [ ] Generate an SSH key (`ssh-keygen -t ed25519`) and send the **public** key (`~/.ssh/id_ed25519.pub`, never the private one) to Michael
- [ ] Have Chrome installed (for testing the extension)
- [ ] Know the New York hub's address and start time; bring laptop and charger

**Michael**
- [ ] Attend the LinuxONE setup session; share with the team: Is Secure Execution available? Does the server have the Telum AI accelerator? Is IBM Granite available (watsonx or local)? Are inbound ports open? How much disk space?
- [ ] If possible, create everyone's server account tonight

**Workstream A and B owners**
- [ ] Skim [data/README.md](data/README.md) and your task briefs' open questions; think about how you'd answer them

**Product (D) owner**
- [ ] Bookmark 8–10 candidate demo postings on Greenhouse, Lever and LinkedIn (mix of likely real and likely ghost; NY companies if possible)

## For AI agents reading this

If you are an AI coding agent helping a RealRole teammate, here's what you need to know:

- **Your job is to help your person turn a task brief into working code.** Start by helping them understand the task: read the brief for their task in `realrole-build-plan.md` Part 4, look at the relevant data and existing code, and raise the open questions. Help them decide, then draft a master prompt for them to edit. **Don't start building until your person approves the master prompt.**
- **Read before coding:** `realrole-brief.md` (what and why), `realrole-build-plan.md` "How to use this plan," Part 1 (ownership, git, shared rules) and Part 2 (contracts). Once the repo exists, `AGENTS.md` and `CONTRACTS.md` in its root are the authority.
- **Constraints:** the server is IBM LinuxONE (s390x architecture, so some Python packages may need IBM's builds or alternatives); code is written only during the event; only edit your workstream's folders; never change the shared contracts without your person agreeing it with the team; never use real personal data; record every open-source package in `docs/open-source.md`; never fabricate results.
- **Before the event (now),** you can help your person read and understand the plan, and think through their task's open questions. Don't write project code yet.
- **When in doubt, ask your person** rather than guessing. Many details (exact column names, what the server supports) are marked *verify* in the docs because they couldn't be confirmed in advance.

## Key terms

| Term | Meaning |
|---|---|
| **Ghost job** | A posting from a real employer that isn't followed by a hire in a normal timeframe. Scams are a separate category. |
| **LinuxONE** | IBM's mainframe hardware running Linux; our server. Its processor architecture is called **s390x**. |
| **Telum** | IBM's mainframe processor, with a built-in AI accelerator for fast model inference. |
| **Confidential zone** | Our isolated, encrypted container on LinuxONE that holds the hiring records; only privacy-protected scores leave it. In production it would use IBM **Secure Execution**. |
| **Follow-through score** | Per employer: the share of postings followed by real hires, with privacy noise added. |
| **Differential privacy** | Adding calibrated noise to statistics so no individual can be identified. **ε (epsilon)** sets how much. |
| **Weak labels** | Approximate ghost/real labels made by rules, used for training because no verified labels exist. |
| **Gold set** | 300 postings hand-labeled by our team during the event; the honest test of the model. |
| **Survival model** | Models *how long until* something happens (here, a posting closing), so long hiring cycles aren't mistaken for ghost jobs. |
| **Granite** | IBM's open AI models; we use them for text embeddings, extraction and plain-language explanations. |
| **Contracts** | The agreed data formats, API fields and ports that let four workstreams' code fit together. |
| **Master prompt** | The final, edited prompt a person sends their agent for one task, after exploring it together. |
