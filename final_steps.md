# Final steps to submission

Everything in code is done and tested. What's left needs a person: the LinuxONE server, screenshots, the video, and submitting.

Work through these in order. Tick each box when it's done.

## 0. Install the extension yourself (everyone, ~10 min)

Each teammate runs the extension on their own laptop. It's loaded "unpacked" (straight from the folder), not from the Chrome Web Store.

**1. Get the code and the Python packages**
```
git pull
pip install -r ml/requirements.txt
```

**2. Get the trained model.** It isn't in git: `ml/models/` is ignored because the file is large. Either:
- ask Rachel for `lgbm_v1.joblib` and put it at `ml/models/lgbm_v1.joblib` (create the `models` folder if needed); or
- train it yourself, which takes about 40 minutes: `python -m ml.run train --model lgbm`

**3. Start the API** from the repo root, and leave that terminal open:
```
python api/main.py --no-granite
```
- `--no-granite` makes every summary instant (a template sentence).
- Without it, the IBM Granite sentence appears after about 20 s. The first time downloads about 2.6 GB.
- Check it's running: http://localhost:8000/health should show `"ok": true`.

**4. Load the extension in Chrome**
1. Open `chrome://extensions`.
2. Turn on **Developer mode** (the switch at the top right).
3. Click **Load unpacked** and choose the repo's **`extension`** folder (the one with `manifest.json` in it).
4. The **RealRole** card appears. Check it says **version 0.2.2** or later.
5. Optional: pin it with the puzzle-piece icon in the toolbar, so the R logo shows next to the address bar.
6. If Chrome asks about site access, allow it on all sites. The extension needs that to see listings on company careers sites. It only acts on pages that contain a job listing.

**5. Check it works**
1. Open http://localhost:8000/demo and click the **scam-style sample**: a red **High scam risk** badge should appear under the title.
2. Click **Why?** to open the side panel with the reasons.
3. Open any real job on Greenhouse, Lever, Workday or a company careers page: a badge should appear, usually green.

**After any `git pull`:** click the **reload ↻** icon on the RealRole card at `chrome://extensions`, then reload your job tabs. Open tabs keep the old version until you reload them.

**If no badge appears,** click the R in the toolbar. The popup says why:

| Popup says | Fix |
|---|---|
| "Can't reach the RealRole API" | Start it: `python api/main.py`. Port 8000 must be free; stop any old server |
| "No job listing on this page" | You're not on a single job, e.g. a list of jobs. Open one job |
| "Job site found, but no listing visible yet" | On Workday, click a job so its full description shows |
| An error from the API | Send the message and the page link to Rachel |

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

## 3b. Field test: find a medium-risk listing (everyone, ~20 min)

Each teammate runs the extension on real listings and finds at least one that scores **medium risk** (amber badge, "Some scam signals", 5–15%). It shows the model doing more than "everything is fine". It also gives us real examples for the video and the model card.

**Setup:** install the extension and start the API as in [step 0](#0-install-the-extension-yourself-everyone-10-min).

**Where to look:** medium risk is uncommon on big-company boards. Try:
- **Smaller employers and staffing agencies:** company careers pages, Greenhouse, Lever, Workday.
- **Remote, part-time or contract roles.**
- **Listings with little company information,** no salary or no logo.
- **Very short listings,** or ones heavy on "earn" or "work from home" wording.
- **LinkedIn:** its listings are read from the page, so it's useful for variety.
- **Pasted text:** you can also paste a listing's text into the lookup site (http://localhost:8501).

**Record each one** in `docs/evidence/field-tests.md` (one row per listing; add a row for any surprising **high** or **low** score too):

| Who | Link | Score / band | Top reasons (from "Why?") | Does it look right to you? |
|---|---|---|---|---|

- [ ] Each teammate: at least **one medium-risk listing**, plus a **screenshot** of its badge and "Why?" panel saved to `docs/evidence/`.
- [ ] Note anything that looks wrong, such as a genuine company scored high, an obvious scam scored low, or a page where no badge appears. Send the link to whoever is fixing bugs.
- [ ] Never paste personal information into the lookup site. Only test public listings.

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

## 4b. Package the extension for judges

The extension stays **unpacked**: judges load the folder, just as we do. Publishing to the Chrome Web Store takes days of review, so it isn't realistic for the datathon.

- [ ] Once the API runs on LinuxONE (step 1), set `API_URL` in `extension/config.js` to the server address.
- [ ] Add that address to `host_permissions` in `extension/manifest.json`, e.g. `"http://<server>:8000/*"`.
- [ ] Zip the `extension/` folder as `realrole-extension.zip` and attach it to the GitHub release or the submission.
- [ ] Add to the README: unzip, then `chrome://extensions` → Developer mode → **Load unpacked** → the unzipped folder.
- [ ] If the server can't be reached publicly, judges can still try it locally: run `python api/main.py` and keep `API_URL` as `http://localhost:8000`. Also say this in the README.

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
