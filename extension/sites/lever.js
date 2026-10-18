// Lever job pages: jobs.lever.co/<company>/<id>.
(function () {
  // --- Selectors (update here when Lever changes its HTML) ---
  const SEL = {
    title: [".posting-headline h2", ".posting-header h2", "h2"],
    company: [".main-header-logo img[alt]", "title"],
    description: [".section-wrapper.page-full-width", '[data-qa="job-description"]', ".content"],
    logo: [".main-header-logo img"],
  };
  // ---------------------------------------------------------------

  RealRoleSites.register({
    source: "lever",
    match: (url) => url.hostname === "jobs.lever.co" && url.pathname.split("/").filter(Boolean).length >= 2,
    getJobPosting(doc) {
      const jp = RealRoleSites.bestJobPosting(doc, SEL);
      if (jp && !(jp.hiringOrganization && jp.hiringOrganization.name)) {
        const img = doc.querySelector(".main-header-logo img[alt]");
        if (img) jp.hiringOrganization = { ...(jp.hiringOrganization || {}), name: img.alt.replace(/\s+logo$/i, "") };
      }
      return jp;
    },
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, SEL.title),
  });
})();
