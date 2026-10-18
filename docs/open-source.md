# Open-source libraries, models and data

This list is required by the competition rules. Add every package and source when you start using it.

## Libraries

| Library | Used for | Link |
|---|---|---|
| pandas | Loading and cleaning the data (`ml/`) | https://github.com/pandas-dev/pandas |
| NumPy | Arrays, bootstrap intervals (`ml/`) | https://github.com/numpy/numpy |
| scikit-learn | Group-aware split, TF-IDF and one-hot features, logistic baseline, calibration, metrics (`ml/`) | https://github.com/scikit-learn/scikit-learn |
| LightGBM | The scam-risk model (`ml/lgbm.py`) | https://github.com/microsoft/LightGBM |
| joblib | Saving and loading trained models (`ml/lgbm.py`, `ml/run.py`) | https://github.com/joblib/joblib |
| Hugging Face Transformers | Running IBM Granite locally (`ml/granite.py`) | https://github.com/huggingface/transformers |
| PyTorch | Backend for Transformers (`ml/granite.py`) | https://github.com/pytorch/pytorch |
| requests | IBM watsonx.ai calls for Granite on LinuxONE (`ml/granite.py`) | https://github.com/psf/requests |
| Pillow | Drawing the logo and extension icons (one-off) | https://github.com/python-pillow/Pillow |
| SciPy | Shape operations for the logo (one-off) | https://github.com/scipy/scipy |

The API (`api/`) and the lookup site (`lookup/`) otherwise use only the Python standard library. The Chrome extension (`extension/`) uses no libraries.

## Models

| Model | Used for | Link |
|---|---|---|
| IBM Granite 3.1 1B-A400M Instruct | One-sentence summaries of the score, run locally | https://huggingface.co/ibm-granite/granite-3.1-1b-a400m-instruct |
| IBM Granite 3 8B Instruct (watsonx.ai) | The same summaries on LinuxONE, through watsonx | https://www.ibm.com/granite |

## Data

| Source | Used for | Link |
|---|---|---|
| Real / Fake Job Posting Prediction (EMSCAD, Kaggle, CC0) | Training and evaluating the model | https://www.kaggle.com/datasets/shivamb/real-or-fake-fake-jobposting-prediction |
| Greenhouse Job Board API | The lookup site reading a Greenhouse listing from its link | https://developers.greenhouse.io/job-board.html |
| Lever Postings API | The lookup site reading a Lever listing from its link | https://github.com/lever/postings-api |
| schema.org JobPosting | The structured data job pages embed, which the extension and lookup site read | https://schema.org/JobPosting |
