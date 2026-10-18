// Reads the job listing on the page, asks the service worker for its ghost-risk score, and shows the badge next to
// the job title. Reads only this page's listing; sends nothing about the person browsing.
(function () {
  const HOST_ID = "realrole-badge-host";
  const state = { key: null, score: null, host: null, floating: false, dismissedKey: null, pending: false };

  function send(msg) {
    try {
      return chrome.runtime.sendMessage(msg);
    } catch {
      return Promise.resolve(null); // extension was reloaded; this page's script is orphaned
    }
  }

  function removeBadge() {
    if (state.host) state.host.remove();
    document.querySelectorAll("#" + HOST_ID).forEach((el) => el.remove());
    state.host = null;
  }

  function clear() {
    removeBadge();
    if (state.key !== null) send({ type: "clear" });
    state.key = null;
    state.score = null;
  }

  const IN_FRAME = window.top !== window;

  async function detect() {
    const site = RealRoleSites.forUrl(location.href);
    if (!site) return clear();
    if (IN_FRAME && site.source !== "greenhouse") return; // in frames, only the embedded Greenhouse job form
    const jobposting = site.getJobPosting(document);
    if (!jobposting || !(jobposting.title || jobposting.description)) {
      if (site.generic) return clear(); // an ordinary page: say nothing
      // A supported job site, but no listing (yet): a search page, or a single-page app still rendering.
      removeBadge();
      const none = "none|" + location.href;
      if (state.key !== none) {
        state.key = none;
        state.score = null;
        send({ type: "noListing", source: site.source });
      }
      return;
    }

    // Re-score when the listing changes (single-page apps swap listings without a page load).
    const key = location.href + "|" + (jobposting.title || "") + "|" + String(jobposting.description || "").length;
    if (key === state.key) {
      if (state.pending || !state.score || key === state.dismissedKey) return;
      const anchor = site.getTitleAnchor(document);
      const attached = state.host && document.contains(state.host);
      if (!attached || (state.floating && anchor)) render(state.score, anchor);
      return;
    }

    removeBadge();
    state.key = key;
    state.score = null;
    state.pending = true;
    const resp = await send({ type: "score", jobposting, source: site.source });
    if (state.key !== key) return; // the page moved on while we waited
    state.pending = false;
    if (!resp || !resp.ok || !resp.score) return;
    state.score = resp.score;
    render(resp.score, site.getTitleAnchor(document));
  }

  function render(score, anchor) {
    removeBadge();
    const v = RealRoleFormat.view(score);
    const host = document.createElement("div");
    host.id = HOST_ID;
    host.style.cssText = "all: initial; display: block;";
    const root = host.attachShadow({ mode: "open" });

    const css = document.createElement("link");
    css.rel = "stylesheet";
    css.href = chrome.runtime.getURL("badge.css");
    root.appendChild(css);

    const floating = !anchor;
    const badge = el("div", `rr-badge rr-${v.color}${floating ? " rr-floating" : ""}`);
    badge.setAttribute("role", "status");

    const mark = el("img", "rr-mark");
    mark.src = chrome.runtime.getURL("icons/logo.png");
    mark.alt = "RealRole";
    const main = el("div", "rr-main");
    const text = el("div", "rr-text");
    text.append(el("strong", "rr-num", v.pctText), ` ghost risk · ${v.word}`);

    const bar = el("div", "rr-bar");
    bar.setAttribute("aria-hidden", "true");
    if (v.threshold != null) {
      const zone = el("div", "rr-range"); // the flagged zone, from the threshold up
      zone.style.left = `${v.threshold * 100}%`;
      zone.style.width = `${(1 - v.threshold) * 100}%`;
      bar.append(zone);
    }
    const fill = el("div", "rr-fill");
    fill.style.width = `${Math.max(v.risk * 100, 1)}%`;
    bar.append(fill);
    main.append(text, bar);

    const why = el("button", "rr-why", "Why?");
    why.type = "button";
    why.addEventListener("click", () => send({ type: "openPanel" }));

    badge.append(mark, main, why);

    if (floating) {
      const close = el("button", "rr-close", "×");
      close.type = "button";
      close.setAttribute("aria-label", "Hide RealRole badge");
      close.addEventListener("click", () => {
        state.dismissedKey = state.key;
        removeBadge();
      });
      badge.append(close);
    }
    root.appendChild(badge);

    if (floating) document.body.appendChild(host);
    else anchor.insertAdjacentElement("afterend", host);
    state.host = host;
    state.floating = floating;
  }

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  // Job sites that are single-page apps (Workday, LinkedIn, Greenhouse's new boards) change the job without a page
  // load: re-check on DOM changes, debounced. Other pages only get a few checks while they finish loading, so
  // ordinary websites aren't watched.
  let timer = null;
  const schedule = () => {
    clearTimeout(timer);
    timer = setTimeout(detect, 400);
  };
  const site = RealRoleSites.forUrl(location.href);
  if (site && !site.generic) {
    new MutationObserver((mutations) => {
      if (mutations.every((m) => state.host && (m.target === state.host || state.host.contains(m.target)))) return;
      schedule();
    }).observe(document.documentElement, { childList: true, subtree: true });
  } else {
    [1500, 4000].forEach((ms) => setTimeout(detect, ms)); // JobPosting data some sites add after load
  }
  window.addEventListener("popstate", schedule);
  detect();
})();
