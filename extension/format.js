// Display helpers shared by the badge, side panel and popup.
// The API's `probability` is the chance a posting leads to a hire; we display the flip of it.
(function () {
  const SUFFIXES = /[\s,]+(inc|incorporated|corp|corporation|co|company|ltd|llc|plc|holdings|group|n\.?a|national association)\.?$/i;

  function displayName(name) {
    if (!name) return "";
    let n = name.trim().replace(/\s*\/\s*[A-Z]{2,}.*$/, ""); // "Inc. / Delaware"
    for (let i = 0; i < 3; i++) n = n.replace(SUFFIXES, "");
    n = n.replace(/[\s,]+$/, "");
    // Fix ALL-CAPS names ("IMPINJ INC" -> "Impinj"), but keep short acronyms like "IBM".
    if (n === n.toUpperCase() && /[A-Z]{2}/.test(n)) {
      n = n
        .split(/(\s+|-)/)
        .map((w) => (w.length <= 3 && /^[A-Z&]+$/.test(w) ? w : w.charAt(0) + w.slice(1).toLowerCase()))
        .join("");
    }
    return n;
  }

  function possessive(name) {
    return /s$/i.test(name) ? `${name}'` : `${name}'s`;
  }

  // Everything the UI shows, from one /score response.
  function view(score) {
    const p = score.probability;
    const [lo, hi] = score.range || [p, p];
    const noHire = 1 - p;
    const bands = self.REALROLE_CONFIG.BANDS;
    const band = noHire < bands.GREEN_BELOW ? "green" : noHire >= bands.RED_FROM ? "red" : "amber";
    const name = displayName(score.company.name);
    const pct = Math.round(noHire * 100);
    const plusMinus = Math.round(((hi - lo) / 2) * 100);
    return {
      name,
      ticker: score.company.ticker,
      sector: score.company.sector,
      band,
      noHire,
      pct,
      plusMinus,
      // Exact range of no_hire (flipped, so the low end comes from the API's high end).
      rangeLow: Math.round((1 - hi) * 100),
      rangeHigh: Math.round((1 - lo) * 100),
      barLow: 1 - hi,
      barHigh: 1 - lo,
      sentence: `${pct}% ± ${plusMinus}% chance ${possessive(name)} postings don't lead to a hire`,
    };
  }

  self.RealRoleFormat = { displayName, possessive, view };
})();
