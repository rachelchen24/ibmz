// Toolbar popup: one-line status for the current tab and a shortcut to the side panel.
(async function () {
  const status = document.getElementById("status");
  const open = document.getElementById("open");
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const state = tab ? await chrome.runtime.sendMessage({ type: "getState", tabId: tab.id }) : null;

  if (!state) {
    status.textContent = "No job listing on this page. Open a listing on Greenhouse, Lever, Workday or LinkedIn.";
    return;
  }
  if (state.status === "no-listing") {
    status.textContent = "Job site found, but no listing visible yet. Open a job so its full description shows.";
    return;
  }
  if (state.status === "error") {
    status.textContent = state.detail || "Couldn't check this listing.";
    return;
  }
  status.textContent = RealRoleFormat.view(state.score).sentence + ".";
  open.hidden = false;
  open.addEventListener("click", () => {
    chrome.sidePanel.open({ tabId: tab.id });
    window.close();
  });
})();
