// Workday career sites: <tenant>.wd<N>.myworkdayjobs.com and wd<N>.myworkdaysite.com. Job pages are .../job/...
// or .../details/... (the split view next to search results). A single-page app, so content.js re-runs detection
// whenever the page changes.
(function () {
  // --- Selectors (update here when Workday changes its HTML) ---
  const SEL = {
    title: ['[data-automation-id="jobPostingHeader"]', 'h2[data-automation-id="jobPostingHeader"]'],
    company: ['meta[property="og:site_name"]'],
    description: ['[data-automation-id="jobPostingDescription"]'],
    logo: ['[data-automation-id="logoImage"]', 'img[alt*="logo" i]'],
  };
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "workday",
    match: (url) => /\.myworkday(jobs|site)\.com$/.test(url.hostname),   // job pages and the job panel on search pages
    getJobPosting(doc) {
      const jp = RealRoleSites.bestJobPosting(doc, SEL);
      if (jp && !(jp.hiringOrganization && jp.hiringOrganization.name)) {
        const site = doc.querySelector('meta[property="og:site_name"]');
        if (site && site.content) jp.hiringOrganization = { ...(jp.hiringOrganization || {}), name: site.content.replace(/\s+careers?$/i, "") };
      }
      return jp;
    },
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, SEL.title),
  });
})();
