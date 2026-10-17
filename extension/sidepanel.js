// "Tell me why" side panel: the full breakdown for the company on the active tab.
const content = document.getElementById("content");

async function activeTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? tab.id : null;
}

async function refresh() {
  const tabId = await activeTabId();
  const state = tabId == null ? null : await chrome.runtime.sendMessage({ type: "getState", tabId });
  if (state && state.score) render(state.score);
  else renderEmpty();
}

function h(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k === "style") e.style.cssText = v;
    else e.setAttribute(k, v);
  }
  for (const c of children.flat()) if (c != null && c !== false) e.append(c);
  return e;
}

function renderEmpty() {
  content.replaceChildren(
    h("div", { class: "empty" },
      h("p", { class: "empty-title" }, "No RealRole data for this page"),
      h("p", {}, "Open a job posting on Greenhouse, Workday or LinkedIn from a company in our dataset, and its details show up here.")
    )
  );
}

function render(score) {
  const v = RealRoleFormat.view(score);
  const isMock = score.model_version === "mock";
  const parts = [];

  if (isMock) {
    parts.push(h("div", { class: "notice" },
      h("strong", {}, "Sample data. "),
      "The scoring model isn't live yet, so the numbers and reasons below are placeholders."));
  }

  parts.push(
    h("section", { class: `summary band-${v.band}` },
      h("h1", {}, v.name),
      h("p", { class: "meta" }, [v.ticker, v.sector].filter(Boolean).join(" · ")),
      h("p", { class: "headline" },
        h("span", { class: "num" }, `${v.pct}% ± ${v.plusMinus}%`),
        ` chance ${RealRoleFormat.possessive(v.name)} postings don't lead to a hire`),
      bar(v),
      h("p", { class: "range" }, `Likely between ${v.rangeLow}% and ${v.rangeHigh}%.`),
      score.summary ? h("p", { class: "lede" }, score.summary) : null
    )
  );

  if (score.sector && score.sector.median != null) {
    const sectorNoHire = Math.round((1 - score.sector.median) * 100);
    const above = score.sector.percentile != null ? 100 - score.sector.percentile : null;
    parts.push(
      h("section", {},
        h("h2", {}, "Compared with its sector"),
        h("p", {}, `Typical ${score.sector.name} company in our dataset: `, h("strong", {}, `${sectorNoHire}%`), "."),
        above != null
          ? h("p", {}, `${v.name}'s chance is higher than about `, h("strong", {}, `${above}%`), ` of ${score.sector.name} companies.`)
          : null
      )
    );
  }

  if (score.reasons && score.reasons.length) {
    parts.push(
      h("section", {},
        h("h2", {}, "Why"),
        h("ul", { class: "reasons" }, score.reasons.map(reason))
      )
    );
  }

  if (score.employer_response) {
    parts.push(
      h("section", {},
        h("h2", {}, `Response from ${v.name}`),
        h("blockquote", { class: "response" }, score.employer_response)
      )
    );
  }

  parts.push(
    h("footer", {},
      h("p", {}, "A company-level likelihood based on public data, not a verdict on this posting."),
      h("p", { class: "fine" },
        score.refreshed_at ? `Refreshed ${formatDate(score.refreshed_at)} · ` : "",
        `Model ${score.model_version || "unknown"}`)
    )
  );

  content.replaceChildren(...parts);
}

function bar(v) {
  return h("div", { class: "bar", "aria-hidden": "true" },
    h("div", { class: "bar-range", style: `left:${v.barLow * 100}%;width:${(v.barHigh - v.barLow) * 100}%` }),
    h("div", { class: "bar-fill", style: `width:${v.noHire * 100}%` })
  );
}

// direction is relative to the API's probability of a hire: "lower" lowers the chance of a hire,
// which raises the number we display.
function reason(r) {
  const raises = r.direction === "lower";
  const evidence = (r.evidence || []).filter((e) => e && typeof e === "object");
  return h("li", { class: raises ? "raises" : "lowers" },
    h("span", { class: "dir" }, raises ? "▲ Raises the chance" : "▼ Lowers the chance"),
    h("p", { class: "reason-text" }, r.text),
    evidence.length
      ? h("details", {},
          h("summary", {}, evidence.length === 1 ? "Source" : `${evidence.length} sources`),
          evidence.map(source))
      : null
  );
}

function source(e) {
  const link = e.source_url
    ? h("a", { href: e.source_url, target: "_blank", rel: "noopener noreferrer" }, hostOf(e.source_url))
    : h("span", { class: "fine" }, "No source link");
  return h("div", { class: "source" },
    e.quote ? h("blockquote", {}, `“${e.quote}”`) : null,
    h("p", { class: "fine" }, link, e.page_date ? ` · ${formatDate(e.page_date)}` : "")
  );
}

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function formatDate(s) {
  const d = new Date(s);
  return isNaN(d) ? s : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

chrome.tabs.onActivated.addListener(refresh);
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "stateChanged") refresh();
});
refresh();
