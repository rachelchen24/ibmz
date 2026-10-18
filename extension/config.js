// RealRole extension settings. The only place the API URL and band colors are defined.
// Loaded as a plain script by the service worker, content scripts, side panel, popup and the lookup site.
self.REALROLE_CONFIG = {
  // RealRole API (api/main.py). Run it locally with: py api/main.py
  API_URL: "http://localhost:8000",

  // The API returns band "low" | "medium" | "high"; these are the color classes in badge.css / report.css.
  BAND_COLORS: { low: "green", medium: "amber", high: "red" },
};
