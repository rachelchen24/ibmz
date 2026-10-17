// Service worker: the only part of the extension that talks to the RealRole API.
// Sends only {company_name, source}. Keeps scores for this browser session only (storage.session),
// never a history of what the person viewed.
importScripts("config.js");

const CFG = self.REALROLE_CONFIG;

function cacheKey(name) {
  return "score:" + name.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

async function fetchScore(company_name, source) {
  const key = cacheKey(company_name);
  const cached = (await chrome.storage.session.get(key))[key];
  if (cached) return cached;

  const res = await fetch(`${CFG.API_URL}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ company_name, source }),
  });
  if (!res.ok) throw new Error(`API returned ${res.status}`);
  const score = await res.json();
  await chrome.storage.session.set({ [key]: score });
  return score;
}

// Dev only: replace the probability and shift the range with it, to preview the color bands.
function applyDevOverride(score) {
  const p = CFG.DEV_FORCE_PROBABILITY;
  if (p == null || !score.in_dataset) return score;
  const shift = p - score.probability;
  const clamp = (x) => Math.min(1, Math.max(0, x));
  return { ...score, probability: p, range: score.range.map((r) => clamp(r + shift)) };
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
    fetchScore(msg.company_name, msg.source)
      .then(async (raw) => {
        const score = applyDevOverride(raw);
        await setTabState(tabId, score.in_dataset ? { score, source: msg.source } : null);
        sendResponse({ ok: true, score });
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

// A full page load starts fresh; the content script reports again if it finds a company.
chrome.tabs.onUpdated.addListener((tabId, info) => {
  if (info.status === "loading") setTabState(tabId, null);
});
chrome.tabs.onRemoved.addListener((tabId) => chrome.storage.session.remove("tab:" + tabId));
