# Final steps to submission

Everything in code is done and tested. What's left needs a person: the LinuxONE server, screenshots, the video, and submitting.

Work through these in order. Tick each box when it's done.

## 1. Deploy to IBM LinuxONE (required, Michael)

The rules require the project to run on the LinuxONE Community Cloud, with screenshots.

- [ ] **Python packages:** on the server, `pip install pandas numpy scikit-learn lightgbm joblib requests`.
  - If **LightGBM** fails to install on s390x, tell the team. The fallback is to retrain with scikit-learn's `HistGradientBoostingClassifier` on SVD-reduced text features (about an hour of work).
- [ ] **Code and model:** copy the repo to the server. Then either copy `ml/models/lgbm_v1.joblib` from a laptop that trained it, or train on the server with `python -m ml.run train --model lgbm` (~40 min).
- [ ] **Granite through watsonx:** PyTorch may not install on s390x, so on LinuxONE Granite runs through IBM watsonx.ai. Set these as environment variables or a podman secret, and never commit them:
  ```
  RR_GRANITE=watsonx
  WATSONX_APIKEY=...      WATSONX_PROJECT_ID=...      WATSONX_URL=https://us-south.ml.cloud.ibm.com
  ```
  This path isn't tested yet (no credentials so far). Check `curl -X POST .../summary` returns `"summary_source": "granite-watsonx:..."`.
- [ ] **Run the API in a container,** with the API as the only published port: `python api/main.py --host 0.0.0.0 --port 8000`.
- [ ] **Point the clients at the server:** set `API_URL` in `extension/config.js` to the server address, or use an SSH tunnel to `localhost:8000` for the demo.
- [ ] **Screenshots** into `docs/evidence/`:
  - `uname -m` showing **s390x**, plus `lscpu`;
  - `podman ps` showing the API container;
  - `curl http://<server>:8000/health`;
  - `curl -X POST http://<server>:8000/score -H "Content-Type: application/json" -d '{"posting": {"title": "Data entry clerk", "description": "Earn weekly from home, send your bank details"}, "pasted": true}'`;
  - the extension showing a badge while connected to the server.
- [ ] Remove "Deployment in progress" from the IBM Z section of `README.md`.

## 2. IBM labs (required, everyone)

- [ ] Each person completes **Predictive AI Hybrid AI scenarios (multi-model)** and **Predictive AI + Generative AI**. Confirm whether the rules want this per person or per team.
- [ ] Save the completion screenshots to `docs/evidence/labs/`.

## 3. Team review (everyone, ~15 min)

- [ ] Everyone reads [`docs/model-card.md`](docs/model-card.md): the results, the fairness table and the limitations. Every number in the video must match it.
- [ ] Agree on the **team name** and replace `Team Name` in the title line at the top of `README.md`. The exact format is `[Team Name_IBM Z Datathon 2026 Project]`.
- [ ] Optional: check the `Team` table in `README.md` (names and roles).

## 4. Record the video (3:00 maximum)

Before recording:
- Start the API **with Granite** (`python api/main.py`, no `--no-granite`) so the Granite sentence shows on screen.
- Ask for one summary first, so the model is loaded (the first one takes about a minute).

| Time | Segment | Show |
|---|---|---|
| 0:00–0:25 | Problem | Job scams look like normal listings; applicants lose money and personal data |
| 0:25–0:50 | Data | 17,880 labeled listings. We split by company, because a random split doubled a naive model's score by memorizing companies |
| 0:50–1:15 | Solution | `docs/architecture.md`: extension → API → LightGBM + reasons → IBM Granite |
| 1:15–2:15 | Demo | http://localhost:8000/demo scam sample → red badge → **Why?** → Granite sentence. Then a real Greenhouse listing (low risk). Then pasted text in the lookup site |
| 2:15–2:50 | IBM Z | LinuxONE screenshots (s390x, the container, `curl /score`); the two IBM labs; Granite on watsonx; privacy (only the listing is sent, nothing stored) |
| 2:50–3:00 | Close | Test results: catches 68% of scams, 2 in 3 flags are real. Plus the honest limits |

- [ ] Record a backup take. Going over 3:00 costs points.

## 5. Make the repo public

- [ ] No secrets in the repo: `git grep -i -E "apikey|api_key|secret|password"` should only find variable names.
- [ ] `ml/models/` is git-ignored; the trained model stays out of the repo.
- [ ] Check that every link in `README.md` and `docs/` opens.
- [ ] Make the GitHub repo public, then check it in a logged-out browser window.

## 6. Submit on Hack2Skill (a person must do this)

- [ ] Title: `[Team Name_IBM Z Datathon 2026 Project]`
- [ ] Video link, repo link, open-source list (`docs/open-source.md`), architecture flowchart (`docs/architecture.md`).
- [ ] Click every link in the submission before sending. **Submit early.** Bot or script submissions are disqualified.

## Already done

| | Where |
|---|---|
| Data audit, cleaning, group-aware split | `ml/AUDIT.md`, `ml/cleaning.py`, `ml/split.py` |
| Logistic baseline + LightGBM, calibrated; threshold chosen on validation | `ml/preprocessing.py`, `ml/lgbm.py`, `ml/run.py` |
| One final test evaluation | `ml/reports/metrics_lgbm_test.json` |
| Fairness check | `ml/fairness.py`, `ml/reports/fairness_lgbm_test.json` |
| Explanations (TreeSHAP) and IBM Granite summaries | `ml/explain.py`, `ml/granite.py` |
| API, extension (listing-level), lookup site, logo | `api/`, `extension/`, `lookup/` |
| Model card, architecture, open-source list, README | `docs/`, `README.md` |
| Tests | `python -m unittest discover -s ml/tests -t .` and `... -s api/tests -t .` |

**Removed during clean-up:** the old company-score pipeline (`collect/`, `verify/`, `dataset/`), the scraped shards and company list, the unused raw datasets (`data/raw/`), and the old RealRole planning docs. All of it is still in git history; restore a file with `git checkout <commit> -- <path>`.
