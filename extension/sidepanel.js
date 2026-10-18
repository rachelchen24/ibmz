// "Why?" side panel: the full analysis (report.js) for the listing on the active tab, or why there isn't one.
const content = document.getElementById("content");
const { h } = RealRoleReport;

async function activeTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? tab.id : null;
}

async function refresh() {
  const tabId = await activeTabId();
  const state = tabId == null ? null : await chrome.runtime.sendMessage({ type: "getState", tabId });
  if (state && state.status === "scored" && state.score) render(state.score);
  else renderEmpty(state);
}

function render(score) {
  content.replaceChildren(RealRoleReport.render(score));
}

function renderEmpty(state) {
  const msg = {
    "no-listing": ["Waiting for a job listing",
      "This is a job site we support, but we can't see a listing on this page yet. Open a job (on Workday, click a job so its full description shows) and this panel fills in."],
    error: ["Couldn't check this listing", (state && state.detail) || "Something went wrong talking to the RealRole API."],
  }[state && state.status] || ["No job listing on this page",
    "Open a job listing on Greenhouse, Lever, Workday or LinkedIn and its scam-risk check shows up here."];
  content.replaceChildren(
    h("div", { class: "empty" }, h("p", { class: "empty-title" }, msg[0]), h("p", {}, msg[1]))
  );
}

chrome.tabs.onActivated.addListener(refresh);
chrome.tabs.onUpdated.addListener((_tabId, info) => {
  if (info.url || info.status === "complete") refresh();
});
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "stateChanged") refresh();
});
refresh();
