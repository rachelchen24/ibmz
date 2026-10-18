// RealRole lookup page: link -> listing (our /resolve) or pasted text -> scam-risk score (the API) -> report.js.
// The Granite summary is requested after the report shows and swapped in when it arrives.
const API = self.REALROLE_CONFIG.API_URL;
const { h } = RealRoleReport;

const $ = (id) => document.getElementById(id);
const form = $("link-form");
const linkInput = $("link");
const pasteBox = $("paste-box");
const pasteWhy = $("paste-why");
const pasteForm = $("paste-form");
const status = $("status");
const result = $("result");

const EXAMPLES = [["Sample scam-style listing", "scam"], ["Sample medium-risk listing", "medium"],
                  ["Sample typical listing", "real"]];

async function postJSON(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function setStatus(text, kind = "") {
  status.className = "status " + kind;
  status.textContent = text;
}

function showPaste(why) {
  pasteWhy.textContent = why || "";
  pasteWhy.hidden = !why;
  pasteBox.hidden = false;
  $("paste-text").focus();
}

let shown = 0; // ignore a slow summary for a report that is no longer on screen

function showReport(score, note) {
  setStatus("");
  pasteBox.hidden = true;
  const report = RealRoleReport.render(score);
  report.classList.add("wide");
  result.replaceChildren(...(note ? [h("p", { class: "matched" }, note)] : []), report);
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function scoreAndShow(body, note) {
  setStatus("Checking the listing…", "loading");
  let score;
  try {
    score = await postJSON(`${API}/score`, body);
  } catch {
    return setStatus("We couldn't reach the RealRole scoring service. Is the API running (py api/main.py)?", "error");
  }
  const id = ++shown;
  const wantGranite = score.summary_source === "template" && score.granite_backend !== "template";
  showReport({ ...score, summary_pending: wantGranite }, note);
  if (!wantGranite) return;
  try {
    const g = await postJSON(`${API}/summary`, { risk: score.risk, flagged: score.flagged, reasons: score.reasons });
    if (id === shown) showReport({ ...score, summary: g.summary, summary_source: g.summary_source }, note);
  } catch {
    if (id === shown) showReport(score, note);
  }
}

// --- link flow ---
async function checkLink(url) {
  result.replaceChildren();
  pasteBox.hidden = true;
  setStatus("Reading the link…", "loading");
  let found;
  try {
    found = await postJSON("/resolve", { url });
  } catch {
    return setStatus("Something went wrong reading that link. Please try again.", "error");
  }
  if (!found.jobposting) {
    setStatus("");
    return showPaste(found.message);
  }
  await scoreAndShow({ jobposting: found.jobposting, source: found.source }, `Read the listing from ${found.method}.`);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const url = linkInput.value.trim();
  if (!url) return;
  history.pushState({}, "", "?url=" + encodeURIComponent(url));
  checkLink(url);
});

// --- pasted text ---
pasteForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const description = $("paste-text").value.trim();
  if (!description) return;
  const title = $("paste-title").value.trim();
  scoreAndShow({ posting: { title: title || undefined, description }, pasted: true, source: "pasted text" },
               "Checked the text you pasted (no logo or other page details).");
});

$("show-paste").addEventListener("click", () => showPaste(""));

// --- examples and deep links ---
$("examples").append(
  "Try: ",
  ...EXAMPLES.flatMap(([label, which], i) => {
    const b = h("button", { type: "button", class: "chip" }, label);
    b.addEventListener("click", async () => {
      try {
        const res = await fetch(`${API}/demo/jobposting?case=${which}`);
        const jobposting = await res.json();
        await scoreAndShow({ jobposting, source: "demo" }, "A made-up sample listing.");
      } catch {
        setStatus("We couldn't reach the RealRole scoring service. Is the API running (py api/main.py)?", "error");
      }
    });
    return i ? [" ", b] : [b];
  })
);

function fromLocation() {
  const q = new URLSearchParams(location.search);
  if (q.get("url")) {
    linkInput.value = q.get("url");
    checkLink(q.get("url"));
  } else {
    result.replaceChildren();
    setStatus("");
  }
}
window.addEventListener("popstate", fromLocation);
fromLocation();
