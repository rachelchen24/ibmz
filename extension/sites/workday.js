// Workday career sites: <tenant>.wd<N>.myworkdayjobs.com. A single-page app, so content.js
// re-runs detection when the page changes.
(function () {
  // --- Selectors (update here when Workday changes its HTML) ---
  const TITLE_SELECTORS = [
    '[data-automation-id="jobPostingHeader"]',
    'h2[data-automation-id="jobPostingHeader"]',
  ];
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "workday",
    match: (url) => url.hostname.endsWith(".myworkdayjobs.com") && /\/job\//.test(url.pathname),
    getCompanyName(doc) {
      const fromLd = RealRoleSites.jsonLdHiringOrg(doc);
      if (fromLd) return fromLd;
      // Fallback: the og:site_name or the page title ("Data Engineer | Acme Careers").
      const site = doc.querySelector('meta[property="og:site_name"]');
      if (site && site.content.trim()) return site.content.trim().replace(/\s+careers?$/i, "");
      return null;
    },
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, TITLE_SELECTORS),
  });
})();
