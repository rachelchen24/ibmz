# RealRole: 3-Minute Video Outline (talking points)

IBM Z Datathon 2026 · Theme 2: AI Secured · Target under 3:00

Every number below comes from `docs/model-card.md` and `README.md`. Items in **[brackets]** still need filling in or checking.

| Time | Speaker | Segment |
|---|---|---|
| 0:00–0:10 | Alan | Hook |
| 0:10–1:00 | Rachel | Problem, idea, data |
| 1:00–1:50 | Olivia | The ML |
| 1:50–2:40 | Michael | LinuxONE, privacy, live demo |
| 2:40–2:55 | Alan | Close |

---

## 0:00–0:10 · Hook (Alan)

- Open on a convincing "work from home, earn weekly" listing
- One line: "Would you apply to this? Thousands of people do, and some lose money and their identity."

> **ON SCREEN:** The demo scam listing at `localhost:8000/demo`, with no badge yet.

---

## 0:10–1:00 · Problem, idea and data (Rachel)

**The problem and impact**
- Job scams look like normal listings, and victims lose money and personal data (bank details, IDs)
- **[Optional: one verified stat on job-scam losses, e.g. FTC; check the source first]**
- Job seekers are often students and new grads applying to hundreds of jobs, with no time to vet each one

**The idea**
- RealRole is a second opinion right on the listing, before you share anything
- A Chrome extension adds a badge on Greenhouse, Lever, Workday and LinkedIn, e.g. "74% scam risk · High"
- **Why?** shows the reasons, and IBM Granite sums them up in one plain sentence
- It's a probability with reasons, never a verdict: "shows signs often seen in scam postings"

**Real data is hard to find**
- No public, current, labeled dataset of real vs. scam listings exists
- LinkedIn and Indeed data are off-limits (their terms ban scraping), and commercial data costs enterprise prices
- The best open option, EMSCAD, has 17,880 listings, but they're from 2012–2014 and only 866 are scams
- We cleaned it: removed 281 duplicates, fixed HTML and encoding, parsed salaries and locations
- **Key finding:** no company has both real and scam listings, so a random split lets a model memorize companies. It **doubled** a naive model's score (0.21 → 0.46). We split by company so our numbers are honest.

**The LinkedIn opportunity**
- LinkedIn already sees what we can't: reported and removed listings, recruiter verification, account age, and how applicants respond
- With a LinkedIn partnership, we'd train on millions of fresh, labeled listings instead of 12-year-old data
- That would make the app far more accurate on today's scams, and it could protect every job seeker on LinkedIn

> **ON SCREEN:** EMSCAD stats, then a chart of random split vs. company split, then a "With LinkedIn data" slide.

---

## 1:00–1:50 · The ML (Olivia)

**The models**
- Two models compared on the same group-aware cross-validation (the IBM multi-model lab): a logistic baseline vs. **LightGBM**
- LightGBM uses the text plus listing details, and was tuned over 20 configurations on 5 folds
- Chosen for better ranking and much better calibration (validation Brier 0.027 vs. 0.049)
- **Calibrated**, so a 70% risk really means about 70%
- Threshold picked on validation only. The test set was scored **once**, at the very end.

**Results (held-out test, companies the model never saw)**
- PR-AUC **0.739**, about **15× better than chance**
- Catches **68%** of scams; **2 in 3** flags are real scams
- Only **1.8%** of genuine listings are wrongly flagged
- 200 real listings from public companies scored live: median risk 0.6%, none flagged

**Explainable AI**
- Exact **TreeSHAP** breaks each score into reasons, quoting words from the listing (e.g. "earn," "home")
- Fields a live page can't show are left out of the score instead of counted as missing, so real listings aren't punished
- **IBM Granite** (the predictive + generative lab) sees only the score and reasons, writes one sentence, and never changes the score
- A wording check blocks any accusation and falls back to a template

**Honest limits** (one sentence)
- Old data, and polished scams with a logo slip through. Remote and part-time listings get more false flags, which the model card reports.

> **ON SCREEN:** `docs/architecture.md` diagram, the results table, then the "Why?" panel with SHAP reasons.

---

## 1:50–2:40 · LinuxONE, privacy and the live demo (Michael)

**Running on IBM LinuxONE**
- The API runs in its own Podman container on LinuxONE, as the only published port
- Granite runs through **IBM watsonx.ai** (Granite 3 8B)
- Scoring takes about **150 ms** per listing, so the badge appears as the page loads
- **[Confirm once deployed: LightGBM built on s390x, or the scikit-learn fallback; latency measured on the server]**

**Privacy by design (Theme 2)**
- The extension sends only the listing's public content, never anything about the person browsing
- The API stores nothing and never logs requests; the lookup site never logs pasted links or text
- Nothing that identifies a job seeker leaves their browser

**Live demo**
- Scam-style listing → red **High** badge → click **Why?** → reasons → the Granite sentence appears
- A real Greenhouse listing → green, low risk
- Paste a listing's text into the lookup site → same report

> **ON SCREEN:** Terminal on LinuxONE: `uname -m` → s390x, `lscpu`, `podman ps`, `curl /health`, `curl /score`. Then the browser demo, with the extension connected to the server.

---

## 2:40–2:55 · Close (Alan)

- RealRole gives job seekers a second opinion before they hand over a bank account or ID
- Explainable, calibrated, and private: innovation without exposure
- With LinkedIn data, it could protect every job seeker on the platform
- "That's RealRole." Show the logo and repo link.

---

## Before recording

- [ ] Fill or cut every **[bracket]**
- [ ] Start the API with Granite and request one summary first, so the model is loaded on camera
- [ ] Show the LinuxONE instance and model on screen (required by the rules)
- [ ] Every number must match `docs/model-card.md`
- [ ] Time a full run-through under 3:00, and record a backup take
