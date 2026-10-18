// Workday career sites: <tenant>.wd<N>.myworkdayjobs.com. A single-page app, so content.js re-runs detection when
// the page changes.
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
    match: (url) => url.hostname.endsWith(".myworkdayjobs.com") && /\/job\//.test(url.pathname),
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
