// Dev only: the API's sample listings at http://localhost:8000/demo/posting (api/main.py). They carry JobPosting
// JSON-LD like a real job site.
(function () {
  RealRoleSites.register({
    source: "demo",
    match: (url) => url.hostname === "localhost" && url.pathname.startsWith("/demo/posting"),
    getJobPosting: (doc) => RealRoleSites.jsonLdJobPosting(doc),
    getTitleAnchor: (doc) => doc.querySelector("h1"),
  });
})();
