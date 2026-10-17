// Dev only: the mock API's sample postings at http://localhost:8000/demo/*.
// They carry Greenhouse-style JobPosting JSON-LD, so this is the Greenhouse reader on localhost.
(function () {
  RealRoleSites.register({
    source: "greenhouse",
    match: (url) => url.hostname === "localhost" && url.pathname.startsWith("/demo/posting"),
    getCompanyName: (doc) => RealRoleSites.jsonLdHiringOrg(doc),
    getTitleAnchor: (doc) => doc.querySelector("h1"),
  });
})();
