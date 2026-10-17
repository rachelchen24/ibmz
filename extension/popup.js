// Toolbar popup: one-line status for the current tab and a shortcut to the side panel.
(async function () {
  const status = document.getElementById("status");
  const open = document.getElementById("open");
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const state = tab ? await chrome.runtime.sendMessage({ type: "getState", tabId: tab.id }) : null;

  if (!state || !state.score) {
    status.textContent = "Not in our dataset yet, or not a job posting we can read.";
    return;
  }
  status.textContent = RealRoleFormat.view(state.score).sentence + ".";
  open.hidden = false;
  open.addEventListener("click", () => {
    chrome.sidePanel.open({ tabId: tab.id });
    window.close();
  });
})();
