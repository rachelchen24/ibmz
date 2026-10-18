// Greenhouse job boards: boards.greenhouse.io and job-boards.greenhouse.io.
(function () {
  // --- Selectors (update here when Greenhouse changes its HTML) ---
  const SEL = {
    title: [".job__title h1", "h1.app-title", "#header h1", "h1"],
    company: [".company-name"],
    description: [".job__description", "#content", ".job-post", "main"],
    logo: [".logo img", "img.logo", "header img", ".job__header img"],
  };
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "greenhouse",
    match: (url) => /(^|\.)greenhouse\.io$/.test(url.hostname) && /\/jobs\/\d+/.test(url.pathname),
    getJobPosting: (doc) => RealRoleSites.bestJobPosting(doc, SEL),
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, SEL.title),
  });
})();
