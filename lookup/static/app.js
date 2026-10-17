// RealRole lookup page: link -> company (our /resolve) -> score (the public API) -> report.js.
const API = self.REALROLE_CONFIG.API_URL;
const { h } = RealRoleReport;

const $ = (id) => document.getElementById(id);
const form = $("link-form");
const linkInput = $("link");
const searchBox = $("company-search");
const searchWhy = $("search-why");
const companyInput = $("company");
const results = $("company-results");
const status = $("status");
const result = $("result");

const EXAMPLES = [
  ["MongoDB on Greenhouse", "https://job-boards.greenhouse.io/mongodb/jobs/7000001"],
  ["CrowdStrike on Workday", "https://crowdstrike.wd5.myworkdayjobs.com/en-US/crowdstrikecareers/job/Remote/Engineer_R1"],
  ["Ally on LinkedIn", "https://www.linkedin.com/jobs/view/data-analyst-at-ally-financial-4000000001"],
];

async function postJSON(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function getJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function setStatus(text, kind = "") {
  status.className = "status " + kind;
  status.textContent = text;
}

function showSearch(why) {
  searchWhy.textContent = why || "";
  searchWhy.hidden = !why;
  searchBox.hidden = false;
  companyInput.focus();
}

function showReport(score, note) {
  setStatus("");
  searchBox.hidden = true;
  const report = RealRoleReport.render(score);
  report.classList.add("wide");
  result.replaceChildren(...(note ? [h("p", { class: "matched" }, note)] : []), report);
  result.scrollIntoView({ behavior: "smooth", block: "start" });
}

// --- link flow ---
async function checkLink(url) {
  result.replaceChildren();
  searchBox.hidden = true;
  setStatus("Reading the link…", "loading");
  let found;
  try {
    found = await postJSON("/resolve", { url });
  } catch {
    return setStatus("Something went wrong reading that link. Please try again.", "error");
  }
  if (!found.company_name) {
    setStatus("");
    return showSearch(found.message);
  }

  setStatus(`Looking up ${found.company_name}…`, "loading");
  let score;
  try {
    score = await postJSON(`${API}/score`, { company_name: found.company_name, source: found.source });
  } catch {
    return setStatus("We couldn't reach the RealRole scoring service. Is the API running?", "error");
  }
  if (!score.in_dataset) {
    setStatus("");
    return showSearch(`${found.company_name} isn't in our dataset yet. If we have it under another name, search for it here.`);
  }
  showReport(score, `Matched “${found.company_name}” from the ${found.method}.`);
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const url = linkInput.value.trim();
  if (!url) return;
  history.pushState({}, "", "?url=" + encodeURIComponent(url));
  checkLink(url);
});

// --- company search fallback ---
let searchTimer = null;
let active = -1;

companyInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 200);
});

companyInput.addEventListener("keydown", (e) => {
  const items = [...results.children];
  if (!items.length) return;
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    active = (active + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
    items.forEach((li, i) => li.setAttribute("aria-selected", String(i === active)));
  } else if (e.key === "Enter" && active >= 0) {
    e.preventDefault();
    items[active].click();
  }
});

async function runSearch() {
  const q = companyInput.value.trim();
  active = -1;
  if (q.length < 2) return renderResults([]);
  try {
    renderResults(await getJSON(`${API}/companies/search?q=${encodeURIComponent(q)}`), q);
  } catch {
    renderResults([]);
  }
}

function renderResults(list, q) {
  companyInput.setAttribute("aria-expanded", String(list.length > 0 || !!q));
  if (!list.length) {
    results.replaceChildren(...(q ? [h("li", { class: "none" }, "No company in our dataset matches that.")] : []));
    return;
  }
  results.replaceChildren(
    ...list.map((c) => {
      const li = h("li", { role: "option", "aria-selected": "false" },
        h("span", {}, RealRoleFormat.displayName(c.name)), h("span", { class: "tick" }, c.ticker));
      li.addEventListener("click", () => openTicker(c.ticker, true));
      return li;
    })
  );
}

async function openTicker(ticker, push) {
  results.replaceChildren();
  companyInput.setAttribute("aria-expanded", "false");
  if (push) history.pushState({}, "", "?ticker=" + encodeURIComponent(ticker));
  setStatus("Loading…", "loading");
  try {
    const score = await getJSON(`${API}/company/${encodeURIComponent(ticker)}`);
    if (!score.in_dataset) return setStatus("That company isn't in our dataset yet.", "error");
    showReport(score);
  } catch {
    setStatus("We couldn't reach the RealRole scoring service. Is the API running?", "error");
  }
}

$("show-search").addEventListener("click", () => showSearch(""));

// --- examples and deep links ---
$("examples").append(
  "Try: ",
  ...EXAMPLES.flatMap(([label, url], i) => {
    const b = h("button", { type: "button", class: "chip" }, label);
    b.addEventListener("click", () => {
      linkInput.value = url;
      form.requestSubmit();
    });
    return i ? [" ", b] : [b];
  })
);

function fromLocation() {
  const q = new URLSearchParams(location.search);
  if (q.get("url")) {
    linkInput.value = q.get("url");
    checkLink(q.get("url"));
  } else if (q.get("ticker")) {
    openTicker(q.get("ticker"), false);
  } else {
    result.replaceChildren();
    setStatus("");
  }
}
window.addEventListener("popstate", fromLocation);
fromLocation();
