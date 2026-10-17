// Site registry and helpers shared by the per-site readers.
// Each site module calls RealRoleSites.register({ source, match, getCompanyName, getTitleAnchor }).
(function () {
  const sites = [];

  function register(site) {
    sites.push(site);
  }

  function forUrl(url) {
    return sites.find((s) => s.match(new URL(url))) || null;
  }

  // Walks JSON-LD blocks (including @graph and arrays) for a JobPosting's hiringOrganization.name.
  function jsonLdHiringOrg(doc) {
    const scripts = doc.querySelectorAll('script[type="application/ld+json"]');
    for (const s of scripts) {
      let data;
      try {
        data = JSON.parse(s.textContent);
      } catch {
        continue;
      }
      const name = findOrg(data, 0);
      if (name) return name;
    }
    return null;
  }

  function findOrg(node, depth) {
    if (!node || typeof node !== "object" || depth > 6) return null;
    if (Array.isArray(node)) {
      for (const item of node) {
        const n = findOrg(item, depth + 1);
        if (n) return n;
      }
      return null;
    }
    const type = [].concat(node["@type"] || []);
    if (type.includes("JobPosting") && node.hiringOrganization) {
      const org = [].concat(node.hiringOrganization)[0];
      const name = typeof org === "string" ? org : org && org.name;
      if (name && name.trim()) return name.trim();
    }
    for (const key of ["@graph", "mainEntity", "itemListElement"]) {
      const n = findOrg(node[key], depth + 1);
      if (n) return n;
    }
    return null;
  }

  // First element matching any selector that has visible text.
  function firstText(doc, selectors) {
    for (const sel of selectors) {
      const el = doc.querySelector(sel);
      if (el && el.textContent.trim()) return el;
    }
    return null;
  }

  self.RealRoleSites = { register, forUrl, jsonLdHiringOrg, firstText };
})();
