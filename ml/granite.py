"""Generative explanation with IBM Granite: the predictive model scores, Granite writes the plain-language summary.

Pairs the two mandatory IBM labs (predictive + generative AI): LightGBM gives the scam-risk probability and its
reasons (ml/explain.py); Granite turns exactly those facts into one sentence. Granite never sees anything else and
never changes the score.

Backends, chosen by RR_GRANITE (default "auto": local if transformers is installed, else watsonx if configured,
else the template):
  local     transformers on CPU/GPU. Model: GRANITE_MODEL, default ibm-granite/granite-3.1-1b-a400m-instruct
            (1B mixture-of-experts, 400M active: ~15 s per summary on a laptop CPU; ~2.6 GB download on first use).
            granite-3.3-2b-instruct writes better but took ~90 s per summary on the same CPU.
  watsonx   IBM watsonx.ai REST API: WATSONX_APIKEY, WATSONX_PROJECT_ID, WATSONX_URL (default us-south), model
            WATSONX_MODEL (default ibm/granite-3-8b-instruct). The route for LinuxONE, where PyTorch wheels may be
            unavailable. Not exercised in tests: it needs IBM Cloud credentials.
  template  no model: a fixed sentence built from the same facts. Always available, used as the fallback.
Every summary reports which backend wrote it (summary_source), so the UI and the video can say so honestly. Granite
output that breaks the wording rules (accusations, speculation, too long, not starting "This posting") is replaced
by the template, and the source then says "template".
"""
import os
import re
import threading

GRANITE_MODEL = os.environ.get("GRANITE_MODEL", "ibm-granite/granite-3.1-1b-a400m-instruct")
WATSONX_MODEL = os.environ.get("WATSONX_MODEL", "ibm/granite-3-8b-instruct")
MAX_WORDS = 45
# A summary describes likelihood and the given signals only: no accusations, no speculation.
FORBIDDEN = re.compile(
    r"\b(is|are) (a |definitely |certainly )?(scam|fraud|fake|criminal|illegal|ghost job)\b|\bscammer|\bfraudster|"
    r"\bguarantee|\bdefinitely\b|\bcertainly\b|\bproven\b|\bred flags?\b|\bsuspicious\b|\bmight not\b|"
    r"\bcompetitive\b|\bvague\b|\bhigher-risk location\b|\bis (a )?(genuine|legitimate|real|safe)\b|"
    r"\bhighly risky\b|\brisky\b", re.I)

SYSTEM = ("You summarize an automated job-posting risk score for a job seeker. Rules: write exactly ONE sentence "
          "of at most 35 words; start it with \"This posting\"; mention only the listed signals, in plain words; do "
          "not add opinions, guesses or facts that are not listed; never say the posting or company is a scam or a ghost job.")
EXAMPLE_IN = ("Verdict: higher risk (72%).\nSignals that raise the risk: no company logo; no salary given.\n"
              "Signals that lower the risk: none.")
EXAMPLE_OUT = "This posting shows signs often seen in ghost listings, mainly the missing company logo and salary."
EXAMPLE2_IN = ("Verdict: lower risk (3%).\nSignals that raise the risk: none.\n"
               "Signals that lower the risk: has a company logo; required education: Bachelor's Degree.")
EXAMPLE2_OUT = "This posting looks like a typical genuine listing: it has a company logo and states the education needed."


def _facts(probability: float, flagged: bool, reasons: list[dict]) -> str:
    ups = [r["text"] for r in reasons if r["direction"] == "raises"][:3]
    downs = [r["text"] for r in reasons if r["direction"] == "lowers"][:3]
    verdict = "higher risk" if flagged else "lower risk"
    return (f"Verdict: {verdict} ({round(100 * probability)}%).\n"
            f"Signals that raise the risk: {'; '.join(ups) if ups else 'none'}.\n"
            f"Signals that lower the risk: {'; '.join(downs) if downs else 'none'}.")


def _messages(facts: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEM},
            {"role": "user", "content": EXAMPLE_IN}, {"role": "assistant", "content": EXAMPLE_OUT},
            {"role": "user", "content": EXAMPLE2_IN}, {"role": "assistant", "content": EXAMPLE2_OUT},
            {"role": "user", "content": facts}]


def template_summary(probability: float, flagged: bool, reasons: list[dict]) -> str:
    def low(t):   # "No company logo" -> "no company logo" mid-sentence
        t = t.rstrip(".")
        return t[0].lower() + t[1:] if t[:2] != t[:2].upper() else t
    ups = [low(r["text"]) for r in reasons if r["direction"] == "raises"][:2]
    downs = [low(r["text"]) for r in reasons if r["direction"] == "lowers"][:2]
    pct = round(100 * probability)
    if flagged:
        why = "; ".join(ups) if ups else "several signals together"
        return (f"This posting shows signs often seen in ghost postings ({pct}% risk): {why}. "
                "Verify the employer through its official website before sharing personal details.")
    why = "; ".join(downs) if downs else "no strong warning signs"
    return f"This posting looks like a typical genuine listing ({pct}% risk): {why}."


def acceptable(text: str) -> bool:
    return bool(text) and text.startswith("This posting") and len(text.split()) <= MAX_WORDS \
        and not FORBIDDEN.search(text)


class _Local:
    _lock = threading.Lock()
    _pipe = None

    @classmethod
    def available(cls) -> bool:
        try:
            import transformers  # noqa: F401
            return True
        except ImportError:
            return False

    @classmethod
    def load(cls):
        with cls._lock:
            if cls._pipe is None:
                from transformers import AutoModelForCausalLM, AutoTokenizer
                tok = AutoTokenizer.from_pretrained(GRANITE_MODEL)
                model = AutoModelForCausalLM.from_pretrained(GRANITE_MODEL, dtype="auto")
                model.eval()
                cls._pipe = (tok, model)
        return cls._pipe

    @classmethod
    def generate(cls, facts: str) -> str:
        tok, model = cls.load()
        import torch
        with cls._lock:   # one generation at a time on CPU
            ids = tok.apply_chat_template(_messages(facts), add_generation_prompt=True, return_tensors="pt",
                                          return_dict=True)
            with torch.no_grad():
                out = model.generate(**ids, max_new_tokens=70, do_sample=False, pad_token_id=tok.eos_token_id)
            return tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()


class _Watsonx:
    @staticmethod
    def available() -> bool:
        return bool(os.environ.get("WATSONX_APIKEY") and os.environ.get("WATSONX_PROJECT_ID"))

    @staticmethod
    def generate(facts: str) -> str:
        import requests
        token = requests.post("https://iam.cloud.ibm.com/identity/token", timeout=30,
                              data={"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                                    "apikey": os.environ["WATSONX_APIKEY"]}).json()["access_token"]
        url = os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com").rstrip("/")
        r = requests.post(f"{url}/ml/v1/text/chat?version=2024-10-08", timeout=60,
                          headers={"Authorization": f"Bearer {token}"},
                          json={"model_id": WATSONX_MODEL, "project_id": os.environ["WATSONX_PROJECT_ID"],
                                "messages": _messages(facts), "max_tokens": 70, "temperature": 0})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()


def backend() -> str:
    mode = os.environ.get("RR_GRANITE", "auto").lower()
    if mode in ("off", "template"):
        return "template"
    if mode == "local" or (mode == "auto" and _Local.available()):
        return "local"
    if mode == "watsonx" or (mode == "auto" and _Watsonx.available()):
        return "watsonx"
    return "template"


def clean_output(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip().strip('"')
    return re.split(r"(?<=[.!?])\s", text)[0]   # first sentence only


def summarize(probability: float, flagged: bool, reasons: list[dict]) -> tuple[str, str]:
    """(summary, source). source is 'granite-local:<model>', 'granite-watsonx:<model>' or 'template' (also used
    when Granite fails or writes something that breaks the wording rules)."""
    b = backend()
    if b != "template":
        try:
            text = clean_output((_Local if b == "local" else _Watsonx).generate(_facts(probability, flagged, reasons)))
            if acceptable(text):
                return text, f"granite-{b}:{GRANITE_MODEL if b == 'local' else WATSONX_MODEL}"
        except Exception:   # a missing model or network must never break scoring
            pass
    return template_summary(probability, flagged, reasons), "template"
