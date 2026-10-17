// RealRole extension settings. The only place the API URL and color bands are defined.
// Loaded as a plain script by the service worker, content scripts, side panel and popup.
self.REALROLE_CONFIG = {
  // Public API (build plan 2.6). The local mock in dev/ serves the same contract on this port.
  API_URL: "http://localhost:8000",

  // Bands on no_hire = 1 - probability (the chance a company's postings don't lead to a hire).
  // no_hire < GREEN_BELOW is green; no_hire >= RED_FROM is red; anything between is amber.
  BANDS: { GREEN_BELOW: 0.40, RED_FROM: 0.65 },

  // Dev only: set to a number between 0 and 1 to replace the API's probability (chance of a hire)
  // so every color band can be previewed. Leave null for real use.
  DEV_FORCE_PROBABILITY: null,
};
