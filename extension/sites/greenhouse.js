// Greenhouse job boards (boards.greenhouse.io, job-boards.greenhouse.io), including the job form companies embed in
// their own careers pages (an iframe on greenhouse.io). Board pages listing many jobs are not a listing.
(function () {
  // --- Selectors (update here when Greenhouse changes its HTML) ---
  const SEL = {
    title: [".job__title h1", "h1.app-title", "#header h1", ".job__title", "h1"],
    company: [".company-name"],
    description: [".job__description", "#content", ".job-post", "main"],
    logo: [".logo img", "img.logo", "header img", ".job__header img"],
  };
  // ---------------------------------------------------------------

  function isJobPage(url) {
    if (/\/jobs\/\d+/.test(url.pathname)) return true; // .../<board>/jobs/<id>
    return /\/embed\/job_app/.test(url.pathname) && (url.searchParams.has("token") || url.searchParams.has("gh_jid"));
  }

  RealRoleSites.register({
    source: "greenhouse",
    match: (url) => /(^|\.)greenhouse\.io$/.test(url.hostname),
    getJobPosting: (doc) => (isJobPage(new URL(doc.location.href)) ? RealRoleSites.bestJobPosting(doc, SEL) : null),
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, SEL.title),
  });
})();
