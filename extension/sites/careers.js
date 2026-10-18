// Any other page that carries a schema.org JobPosting (most company careers sites do, so Google can list their
// jobs). Registered last: the named sites above take precedence. Uses the page's own JobPosting data only, never
// guesses a listing from arbitrary text, so ordinary pages are left alone and nothing is sent for them.
(function () {
  RealRoleSites.register({
    source: "careers site",
    generic: true,
    match: () => true,
    getJobPosting: (doc) => RealRoleSites.jsonLdJobPosting(doc),
    getTitleAnchor: (doc) => RealRoleSites.firstText(doc, ["h1"]),
  });
})();
