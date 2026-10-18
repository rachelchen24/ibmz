# Submission checklist (IBM Z Datathon 2026)

From the official rules and the build plan, with what's done and what's left.

## Required

- [ ] **Demo video, 3:00 maximum.** Required content in order: the problem, supporting data, the solution, the demo, how RealRole uses IBM Z.
- [ ] **Public GitHub repo** with all code, and links to every library and data source.
  - The list is done: [`docs/open-source.md`](open-source.md).
  - **Before making the repo public**, remove or slim `data/collect/shard_*/postings_*.jsonl`. Those files hold full job descriptions, and we publish indicators and short quotes, not page copies.
- [ ] **Title, in exactly this format:** `[Team Name_IBM Z Datathon 2026 Project]`
- [x] **Architecture flowchart:** [`docs/architecture.md`](architecture.md) (Mermaid, which GitHub renders).
- [x] **Working prototype:** the API, extension and lookup site run locally. See "Run the demo" below.
- [ ] **Runs on LinuxONE, with screenshots.** This is the server step, still open. See `docs/architecture.md` § Deployment.
- [ ] **Submitted by a person** on Hack2Skill, with every link checked live.
- [ ] **Both IBM labs completed.** Save completion screenshots to `docs/evidence/labs/`.

## Done in code

| Item | Where |
|---|---|
| Data audit, cleaning, group-aware split | `ml/AUDIT.md`, `ml/cleaning.py`, `ml/split.py` |
| Models: baseline + LightGBM, calibrated | `ml/preprocessing.py`, `ml/lgbm.py` |
| One final test evaluation | `ml/reports/metrics_lgbm_test.json`: PR-AUC 0.739, precision 66% / recall 68% |
| Fairness check | `ml/fairness.py`, `ml/reports/fairness_lgbm_test.json` |
| Model card | `docs/model-card.md` |
| Explanations (TreeSHAP) + IBM Granite summary | `ml/explain.py`, `ml/granite.py` |
| API | `api/main.py` + `api/README.md` |
| Extension (listing-level) | `extension/` |
| Lookup site (link or pasted text) | `lookup/` |
| Tests | `python -m unittest discover -s {ml,api,collect,verify,dataset}/tests -t .` |

## Run the demo (locally)

```
py api/main.py                    # http://localhost:8000; first Granite summary downloads ~2.6 GB
py lookup/app.py                  # http://localhost:8501
```

Then:
1. Load `extension/` unpacked in Chrome (`chrome://extensions` → Developer mode → Load unpacked).
2. Open http://localhost:8000/demo and click the scam-style sample: the badge shows **High scam risk**.
3. Click **Why?** for the reasons. The Granite summary appears after about 20 s.
4. Try a real Greenhouse or Lever listing.

## Video outline (3:00)

| Time | Segment | Shows |
|---|---|---|
| 0:00–0:25 | Problem | Job scams target job seekers, often with listings that look normal |
| 0:25–0:50 | Data | 17,880 labeled listings. Why we split by company: random splits double the score by memorizing companies |
| 0:50–1:15 | Solution | Architecture diagram: extension → API → LightGBM + reasons → Granite summary |
| 1:15–2:15 | Demo | Scam-style listing flagged, with "Why?" reasons and the Granite sentence; a real Greenhouse listing scored low; pasted text in the lookup site |
| 2:15–2:50 | IBM Z | LinuxONE screenshots (s390x, the container, `curl /score`); predictive + generative labs; Granite on watsonx |
| 2:50–3:00 | Close | Test results (catches 68% of scams, 2 in 3 flags are scams) and the honest limits |

Check every number in the video against `docs/model-card.md`.
