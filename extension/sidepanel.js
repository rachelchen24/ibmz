// "Tell me why" side panel: the full analysis (report.js) for the company on the active tab.
const content = document.getElementById("content");
const { h } = RealRoleReport;

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

function render(score) {
  content.replaceChildren(RealRoleReport.render(score));
}

function renderEmpty() {
  content.replaceChildren(
    h("div", { class: "empty" },
      h("p", { class: "empty-title" }, "No RealRole data for this page"),
      h("p", {}, "Open a job posting on Greenhouse, Workday or LinkedIn from a company in our dataset, and its details show up here.")
    )
  );
}

chrome.tabs.onActivated.addListener(refresh);
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "stateChanged") refresh();
});
refresh();
