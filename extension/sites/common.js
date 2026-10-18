// Site registry and helpers shared by the per-site readers.
// Each site module calls RealRoleSites.register({ source, match, getJobPosting, getTitleAnchor }).
// getJobPosting returns a schema.org JobPosting object: the page's own JSON-LD when it has one, otherwise one
// built from the visible title, company, description and logo. Only this listing's public content is read.
(function () {
  const sites = [];

  function register(site) {
    sites.push(site);
  }

  function forUrl(url) {
    return sites.find((s) => s.match(new URL(url))) || null;
  }

  // The page's JSON-LD JobPosting (including inside @graph and arrays), or null.
  function jsonLdJobPosting(doc) {
    for (const s of doc.querySelectorAll('script[type="application/ld+json"]')) {
      let data;
      try {
        data = JSON.parse(s.textContent);
      } catch {
        continue;
      }
      const jp = findJobPosting(data, 0);
      if (jp && (jp.title || jp.description)) return jp;
    }
    return null;
  }

  function findJobPosting(node, depth) {
    if (!node || typeof node !== "object" || depth > 6) return null;
    if (Array.isArray(node)) {
      for (const item of node) {
        const jp = findJobPosting(item, depth + 1);
        if (jp) return jp;
      }
      return null;
    }
    if ([].concat(node["@type"] || []).includes("JobPosting")) return node;
    for (const key of ["@graph", "mainEntity", "itemListElement"]) {
      const jp = findJobPosting(node[key], depth + 1);
      if (jp) return jp;
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

  // A JobPosting built from what's visible, for pages without JSON-LD (or with an incomplete one).
  function domJobPosting(doc, sel) {
    const title = firstText(doc, sel.title || []);
    const desc = firstText(doc, sel.description || []);
    if (!title && !desc) return null;
    const company = firstText(doc, sel.company || []);
    const logo = (sel.logo || []).some((s) => doc.querySelector(s));
    return {
      "@type": "JobPosting",
      title: title ? title.textContent.trim() : undefined,
      description: desc ? desc.innerText.trim().slice(0, 20000) : undefined,
      hiringOrganization: {
        name: company ? company.textContent.trim().replace(/^at\s+/i, "") : undefined,
        logo: logo ? "present" : undefined,
      },
    };
  }

  const norm = (s) => String(s || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

  // JSON-LD when present, with any missing title/description filled from the page. Single-page sites (Workday)
  // can keep the first job's JSON-LD while showing another job: if the visible title differs, trust the page.
  function bestJobPosting(doc, sel) {
    const ld = jsonLdJobPosting(doc);
    const dom = domJobPosting(doc, sel);
    if (!ld) return dom;
    if (dom && dom.title && ld.title && norm(dom.title) !== norm(ld.title)) return dom;
    return { ...ld, title: ld.title || (dom && dom.title), description: ld.description || (dom && dom.description) };
  }

  self.RealRoleSites = { register, forUrl, jsonLdJobPosting, domJobPosting, bestJobPosting, firstText };
})();
