// The full RealRole analysis for one /score response, as DOM nodes. Shared by the extension's
// side panel and the lookup website (lookup/ serves this file), so both always look the same.
// Needs config.js and format.js loaded first.
(function () {
  function h(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v;
      else if (k === "style") e.style.cssText = v;
      else e.setAttribute(k, v);
    }
    for (const c of children.flat()) if (c != null && c !== false) e.append(c);
    return e;
  }

  // Returns a <div class="rr-report"> holding the whole analysis.
  function render(score) {
    const v = RealRoleFormat.view(score);
    const parts = [];

    if (score.model_version === "mock") {
      parts.push(h("div", { class: "rr-notice" },
        h("strong", {}, "Sample data. "),
        "The scoring model isn't live yet, so the numbers and reasons below are placeholders."));
    }

    parts.push(
      h("section", { class: `rr-summary rr-band-${v.band}` },
        h("h1", {}, v.name),
        h("p", { class: "rr-meta" }, [v.ticker, v.sector].filter(Boolean).join(" · ")),
        h("p", { class: "rr-headline" },
          h("span", { class: "rr-num" }, `${v.pct}% ± ${v.plusMinus}%`),
          ` chance ${RealRoleFormat.possessive(v.name)} postings don't lead to a hire`),
        bar(v),
        h("p", { class: "rr-range" }, `Likely between ${v.rangeLow}% and ${v.rangeHigh}%.`),
        score.summary ? h("p", { class: "rr-lede" }, score.summary) : null
      )
    );

    if (score.sector && score.sector.median != null) {
      const sectorNoHire = Math.round((1 - score.sector.median) * 100);
      const above = score.sector.percentile != null ? 100 - score.sector.percentile : null;
      parts.push(
        h("section", { class: "rr-sector" },
          h("h2", {}, "Compared with its sector"),
          h("p", {}, `Typical ${score.sector.name} company in our dataset: `, h("strong", {}, `${sectorNoHire}%`), "."),
          above != null
            ? h("p", {}, `${v.name}'s chance is higher than about `, h("strong", {}, `${above}%`), ` of ${score.sector.name} companies.`)
            : null
        )
      );
    }

    if (score.reasons && score.reasons.length) {
      parts.push(
        h("section", { class: "rr-why-list" },
          h("h2", {}, "Why"),
          h("ul", { class: "rr-reasons" }, score.reasons.map(reason))
        )
      );
    }

    if (score.employer_response) {
      parts.push(
        h("section", { class: "rr-employer" },
          h("h2", {}, `Response from ${v.name}`),
          h("blockquote", { class: "rr-response" }, score.employer_response)
        )
      );
    }

    parts.push(
      h("footer", { class: "rr-foot" },
        h("p", {}, "A company-level likelihood based on public data, not a verdict on any one posting."),
        h("p", { class: "rr-fine" },
          score.refreshed_at ? `Refreshed ${formatDate(score.refreshed_at)} · ` : "",
          `Model ${score.model_version || "unknown"}`)
      )
    );

    return h("div", { class: `rr-report rr-band-${v.band}` }, parts);
  }

  function bar(v) {
    return h("div", { class: "rr-bar", "aria-hidden": "true" },
      h("div", { class: "rr-bar-range", style: `left:${v.barLow * 100}%;width:${(v.barHigh - v.barLow) * 100}%` }),
      h("div", { class: "rr-bar-fill", style: `width:${v.noHire * 100}%` })
    );
  }

  // direction is relative to the API's probability of a hire: "lower" lowers the chance of a hire,
  // which raises the number we display.
  function reason(r) {
    const raises = r.direction === "lower";
    const evidence = (r.evidence || []).filter((e) => e && typeof e === "object");
    return h("li", { class: raises ? "rr-raises" : "rr-lowers" },
      h("span", { class: "rr-dir" }, raises ? "▲ Raises the chance" : "▼ Lowers the chance"),
      h("p", { class: "rr-reason-text" }, r.text),
      evidence.length
        ? h("details", {},
            h("summary", {}, evidence.length === 1 ? "Source" : `${evidence.length} sources`),
            evidence.map(source))
        : null
    );
  }

  function source(e) {
    const link = e.source_url
      ? h("a", { href: e.source_url, target: "_blank", rel: "noopener noreferrer" }, hostOf(e.source_url))
      : h("span", { class: "rr-fine" }, "No source link");
    return h("div", { class: "rr-source" },
      e.quote ? h("blockquote", {}, `“${e.quote}”`) : null,
      h("p", { class: "rr-fine" }, link, e.page_date ? ` · ${formatDate(e.page_date)}` : "")
    );
  }

  function hostOf(url) {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return url;
    }
  }

  function formatDate(s) {
    const d = new Date(s);
    return isNaN(d) ? s : d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  self.RealRoleReport = { render, h };
})();
