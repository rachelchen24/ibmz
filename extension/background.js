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

// A tab's state belongs to one page. Single-page job sites (Workday, LinkedIn) change the URL without reloading,
// so the state remembers its URL and is ignored once the tab shows a different page.
function samePage(a, b) {
  const strip = (u) => String(u || "").split("#")[0];
  return strip(a) === strip(b);
}

async function postJSON(path, body) {
  let res;
  try {
    res = await fetch(`${CFG.API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch {
    throw new Error(`Can't reach the RealRole API at ${CFG.API_URL}. Is it running? (py api/main.py)`);
  }
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json()).error || "";
    } catch {}
    throw new Error(`The RealRole API returned an error (${res.status}${detail ? ": " + detail : ""}).`);
  }
  return res.json();
}

async function fetchScore(jobposting, source) {
  const key = cacheKey(jobposting);
  const cached = (await chrome.storage.session.get(key))[key];
  if (cached) return { key, score: cached };
  const score = await postJSON("/score", { jobposting, source });
  if (typeof score.risk !== "number") {
    // An old or different server on API_URL (e.g. the retired mock): show nothing rather than a fake 0%.
    throw new Error(`The server at ${CFG.API_URL} isn't the RealRole ghost-risk API. Run: py api/main.py`);
  }
  await chrome.storage.session.set({ [key]: score });
  return { key, score };
}

async function setTabState(tabId, value) {
  const key = "tab:" + tabId;
  if (value) await chrome.storage.session.set({ [key]: value });
  else await chrome.storage.session.remove(key);
  // Tell an open side panel or popup; nobody listening is fine.
  chrome.runtime.sendMessage({ type: "stateChanged", tabId }).catch(() => {});
}

async function getTabState(tabId) {
  const key = "tab:" + tabId;
  const state = (await chrome.storage.session.get(key))[key] || null;
  if (!state) return null;
  try {
    const tab = await chrome.tabs.get(tabId);
    // Chrome hides tab.url for sites without host permission; then trust the state (the content script clears it).
    if (tab.url && state.url && !samePage(state.url, tab.url)) return null; // the tab has moved on to another page
  } catch {
    return null;
  }
  return state;
}

// The Granite summary is slow (seconds on CPU), so it is fetched after the badge shows and swapped in.
async function addGraniteSummary(tabId, url, key, score) {
  if (score.summary_source !== "template" || score.granite_backend === "template") return;
  await setTabState(tabId, { url, status: "scored", score: { ...score, summary_pending: true } });
  try {
    const g = await postJSON("/summary", { risk: score.risk, flagged: score.flagged, reasons: score.reasons });
    const updated = { ...score, summary: g.summary, summary_source: g.summary_source, summary_pending: false };
    await chrome.storage.session.set({ [key]: updated });
    await setTabState(tabId, { url, status: "scored", score: updated });
  } catch (err) {
    console.warn("RealRole: summary request failed:", err.message);
    await setTabState(tabId, { url, status: "scored", score: { ...score, summary_pending: false } });
  }
}

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const tabId = msg.tabId ?? sender.tab?.id;
  const url = sender.tab?.url;

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
        await setTabState(tabId, { url, status: "scored", score });
        sendResponse({ ok: true, score });
        addGraniteSummary(tabId, url, key, score);
      })
      .catch(async (err) => {
        console.warn("RealRole:", err.message);
        await setTabState(tabId, { url, status: "error", detail: err.message });
        sendResponse({ ok: false, error: err.message });
      });
    return true;
  }

  if (msg.type === "noListing") {
    // A supported job site, but no listing on this page yet (e.g. a search page, or still loading).
    setTabState(tabId, { url, status: "no-listing", source: msg.source }).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (msg.type === "clear") {
    setTabState(tabId, null).then(() => sendResponse({ ok: true }));
    return true;
  }

  if (msg.type === "getState") {
    getTabState(tabId).then(sendResponse);
    return true;
  }
});

chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove("tab:" + tabId));
