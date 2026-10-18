// Service worker: the only part of the extension that talks to the RealRole API.
// Sends only the listing's public content ({jobposting, source}). Keeps scores for this browser session only
// (storage.session), never a history of what the person viewed.
importScripts("config.js");

const CFG = self.REALROLE_CONFIG;

function hash(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

function cacheKey(jobposting) {
  return "score:" + hash(JSON.stringify([jobposting.title, jobposting.description, jobposting.hiringOrganization]));
}

async function postJSON(path, body) {
  const res = await fetch(`${CFG.API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API returned ${res.status}`);
  return res.json();
}

async function fetchScore(jobposting, source) {
  const key = cacheKey(jobposting);
  const cached = (await chrome.storage.session.get(key))[key];
  if (cached) return { key, score: cached };
  const score = await postJSON("/score", { jobposting, source });
  if (typeof score.risk !== "number") {
    // An old or different server on API_URL (e.g. the retired mock): show nothing rather than a fake 0%.
    throw new Error(`the server at ${CFG.API_URL} isn't the RealRole scam-risk API (no "risk" in its reply). Run: py api/main.py`);
  }
  await chrome.storage.session.set({ [key]: score });
  return { key, score };
}

// The Granite summary is slow (seconds on CPU), so it is fetched after the badge shows and swapped in.
async function addGraniteSummary(tabId, key, score) {
  if (score.summary_source !== "template" || score.granite_backend === "template") return;
  await setTabState(tabId, { score: { ...score, summary_pending: true } });
  try {
    const g = await postJSON("/summary", { risk: score.risk, flagged: score.flagged, reasons: score.reasons });
    const updated = { ...score, summary: g.summary, summary_source: g.summary_source, summary_pending: false };
    await chrome.storage.session.set({ [key]: updated });
    await setTabState(tabId, { score: updated });
  } catch (err) {
    console.warn("RealRole: summary request failed:", err.message);
    await setTabState(tabId, { score: { ...score, summary_pending: false } });
  }
}

async function setTabState(tabId, value) {
  const key = "tab:" + tabId;
  if (value) await chrome.storage.session.set({ [key]: value });
  else await chrome.storage.session.remove(key);
  // Tell an open side panel or popup; nobody listening is fine.
  chrome.runtime.sendMessage({ type: "stateChanged", tabId }).catch(() => {});
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const tabId = msg.tabId ?? sender.tab?.id;

  if (msg.type === "openPanel") {
    // Must be called synchronously inside the click's user gesture, before any await.
    chrome.sidePanel.open({ tabId }).then(
      () => sendResponse({ ok: true }),
      (err) => sendResponse({ ok: false, error: String(err) })
    );
    return true;
  }

  if (msg.type === "score") {
    fetchScore(msg.jobposting, msg.source)
      .then(async ({ key, score }) => {
        await setTabState(tabId, { score });
        sendResponse({ ok: true, score });
        addGraniteSummary(tabId, key, score);
      })
      .catch(async (err) => {
        console.warn("RealRole: score request failed:", err.message);
        await setTabState(tabId, null);
        sendResponse({ ok: false });
      });
    return true;
  }

  if (msg.type === "clear") {
    setTabState(tabId, null).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (msg.type === "getState") {
    const key = "tab:" + tabId;
    chrome.storage.session.get(key).then((r) => sendResponse(r[key] || null));
    return true;
  }
});

// A full page load starts fresh; the content script reports again if it finds a listing.
chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "loading") setTabState(tabId, null);
});
chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove("tab:" + tabId));
