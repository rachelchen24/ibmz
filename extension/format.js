// Display helpers shared by the badge, side panel, popup and lookup site.
// The API's `risk` is the probability that the listing is a scam posting (calibrated, 0 to 1).
(function () {
  const SUFFIXES = /[\s,]+(inc|incorporated|corp|corporation|co|company|ltd|llc|plc|holdings|group)\.?$/i;

  function displayName(name) {
    if (!name) return "";
    let n = name.trim();
    for (let i = 0; i < 3; i++) n = n.replace(SUFFIXES, "").replace(/[\s,&/]+$/, "");
    return n;
  }

  const BAND_WORDS = { low: "Low scam risk", medium: "Some scam signals", high: "High scam risk" };

  // Everything the UI shows, from one /score response.
  function view(score) {
    const band = score.band || "low";
    const pct = score.risk_pct != null ? score.risk_pct : Math.round((score.risk || 0) * 100);
    const listing = score.listing || {};
    return {
      band,
      color: self.REALROLE_CONFIG.BAND_COLORS[band] || "amber",
      pct,
      risk: score.risk || 0,
      threshold: score.threshold,
      word: BAND_WORDS[band] || score.label,
      title: listing.title || "This listing",
      company: displayName(listing.company),
      sentence: `${pct}% scam risk: ${(BAND_WORDS[band] || "").toLowerCase()}`,
    };
  }

  self.RealRoleFormat = { displayName, view };
})();
