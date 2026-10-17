// Greenhouse job boards: boards.greenhouse.io and job-boards.greenhouse.io.
(function () {
  // --- Selectors (update here when Greenhouse changes its HTML) ---
  const TITLE_SELECTORS = [
    ".job__title h1", // job-boards.greenhouse.io
    "h1.app-title", // boards.greenhouse.io (older layout)
    "#header h1",
    "h1",
  ];
  const COMPANY_SELECTORS = [
    ".company-name", // boards.greenhouse.io: "at Acme Corp"
  ];
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "greenhouse",
    match: (url) => /(^|\.)greenhouse\.io$/.test(url.hostname) && /\/jobs\/\d+/.test(url.pathname),
    getCompanyName(doc) {
      const fromLd = RealRoleSites.jsonLdHiringOrg(doc);
      if (fromLd) return fromLd;
      const el = RealRoleSites.firstText(doc, COMPANY_SELECTORS);
      if (el) return el.textContent.trim().replace(/^at\s+/i, "");
      // Page titles look like "Job Application for Data Engineer at Acme Corp".
      const m = doc.title.match(/\bat\s+(.+?)\s*$/i);
      return m ? m[1] : null;
    },
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, TITLE_SELECTORS),
  });
})();
