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

  const BAND_WORDS = { low: "Low ghost risk", medium: "Some ghost signals", high: "High ghost risk" };

  // Everything the UI shows, from one /score response.
  function view(score) {
    const band = score.band || "low";
    const pct = Math.round((score.risk || 0) * 100);
    const pctText = score.risk > 0 && score.risk < 0.005 ? "<1%" : `${pct}%`;   // genuine listings are often < 1%
    const listing = score.listing || {};
    return {
      band,
      color: self.REALROLE_CONFIG.BAND_COLORS[band] || "amber",
      pct,
      pctText,
      risk: score.risk || 0,
      threshold: score.threshold,
      word: BAND_WORDS[band] || score.label,
      title: listing.title || "This listing",
      company: displayName(listing.company),
      sentence: `${pctText} ghost risk: ${(BAND_WORDS[band] || "").toLowerCase()}`,
    };
  }

  self.RealRoleFormat = { displayName, view };
})();
