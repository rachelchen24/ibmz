// LinkedIn job pages (logged in and logged out). The signed-in view has no JobPosting JSON-LD, so the listing is
// read from the visible page. These selectors are the most likely to break.
(function () {
  // --- Selectors (update here when LinkedIn changes its HTML) ---
  const SEL = {
    title: [
      ".job-details-jobs-unified-top-card__job-title h1",
      ".job-details-jobs-unified-top-card__job-title",
      ".jobs-unified-top-card__job-title",
      ".top-card-layout__title", // logged-out job page
      ".jobs-details h1",
    ],
    company: [
      ".job-details-jobs-unified-top-card__company-name a",
      ".job-details-jobs-unified-top-card__company-name",
      ".jobs-unified-top-card__company-name a",
      ".topcard__org-name-link", // logged-out job page
    ],
    description: [".jobs-description__content", ".jobs-box__html-content", ".show-more-less-html__markup",
                  "#job-details"],
    logo: [".job-details-jobs-unified-top-card__container--two-pane img", ".jobs-unified-top-card img",
           ".top-card-layout__entity-image", ".artdeco-entity-image"],
  };
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "linkedin",
    match: (url) => /(^|\.)linkedin\.com$/.test(url.hostname) && url.pathname.startsWith("/jobs"),
    getJobPosting: (doc) => RealRoleSites.bestJobPosting(doc, SEL),
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, SEL.title),
  });
})();
