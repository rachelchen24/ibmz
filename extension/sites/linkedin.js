// LinkedIn job pages (logged in and logged out). No JobPosting JSON-LD for the signed-in view,
// so the employer comes from the visible top card. These selectors are the most likely to break.
(function () {
  // --- Selectors (update here when LinkedIn changes its HTML) ---
  const TITLE_SELECTORS = [
    ".job-details-jobs-unified-top-card__job-title h1",
    ".job-details-jobs-unified-top-card__job-title",
    ".jobs-unified-top-card__job-title",
    ".top-card-layout__title", // logged-out job page
    ".jobs-details h1",
  ];
  const COMPANY_SELECTORS = [
    ".job-details-jobs-unified-top-card__company-name a",
    ".job-details-jobs-unified-top-card__company-name",
    ".jobs-unified-top-card__company-name a",
    ".jobs-unified-top-card__company-name",
    ".topcard__org-name-link", // logged-out job page
    'a[data-tracking-control-name="public_jobs_topcard-org-name"]',
  ];
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "linkedin",
    match: (url) => /(^|\.)linkedin\.com$/.test(url.hostname) && url.pathname.startsWith("/jobs"),
    getCompanyName(doc) {
      const el = RealRoleSites.firstText(doc, COMPANY_SELECTORS);
      if (el) return el.textContent.trim();
      // Logged-out pages sometimes carry JSON-LD.
      const fromLd = RealRoleSites.jsonLdHiringOrg(doc);
      if (fromLd) return fromLd;
      // ARIA label on the company logo link: "Company, Acme Corp."
      const aria = doc.querySelector('.jobs-details [aria-label^="Company, "]');
      return aria ? aria.getAttribute("aria-label").replace(/^Company,\s*/, "").replace(/\.$/, "") : null;
    },
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, TITLE_SELECTORS),
  });
})();
