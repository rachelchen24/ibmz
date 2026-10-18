// The full RealRole analysis for one listing (/score response), as DOM nodes. Shared by the extension's side
// panel and the lookup website (lookup/ serves this file), so both always look the same.
// Needs config.js and format.js loaded first.
(function () {
  const FIELD_NAMES = {
    company_profile: "company description", requirements: "requirements", benefits: "benefits",
    has_questions: "screening questions", required_experience: "experience level", department: "department",
    function: "job function", salary_range: "salary", employment_type: "employment type",
    required_education: "education", industry: "industry", telecommuting: "remote work",
    has_company_logo: "company logo",
  };

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

  function summarySource(score) {
    const src = score.summary_source || "template";
    if (src.startsWith("granite")) {
      const model = src.split(":")[1] || "Granite";
      return `Summary written by IBM Granite (${model.replace("ibm-granite/", "")}) from the reasons below.`;
    }
    if (score.summary_pending) return "IBM Granite is writing a summary…";
    return "Summary from a fixed template (IBM Granite unavailable or its draft didn't pass our wording check).";
  }

  // Returns a <div class="rr-report"> holding the whole analysis.
  function render(score) {
    const v = RealRoleFormat.view(score);
    const parts = [];

    parts.push(
      h("section", { class: `rr-summary rr-band-${v.color}` },
        h("h1", {}, v.title),
        h("p", { class: "rr-meta" }, [v.company, score.listing && score.listing.source].filter(Boolean).join(" · ")),
        h("p", { class: "rr-headline" }, h("span", { class: "rr-num" }, v.pctText), ` ghost risk · ${v.word}`),
        bar(v),
        v.threshold != null
          ? h("p", { class: "rr-range" }, `Flagged at ${Math.round(v.threshold * 100)}% or more.`)
          : null,
        score.summary ? h("p", { class: "rr-lede" }, score.summary) : null,
        score.summary ? h("p", { class: "rr-fine" }, summarySource(score)) : null
      )
    );

    if (score.reasons && score.reasons.length) {
      parts.push(
        h("section", { class: "rr-why-list" },
          h("h2", {}, "Why"),
          h("ul", { class: "rr-reasons" }, score.reasons.map(reason))
        )
      );
    }

    const leftOut = (score.left_out || []).map((f) => FIELD_NAMES[f] || f);
    const unknown = (score.unknown_inputs || []).filter((f) => !(score.left_out || []).includes(f))
      .map((f) => FIELD_NAMES[f] || f);
    if (leftOut.length || unknown.length) {
      parts.push(
        h("section", { class: "rr-sector" },
          h("h2", {}, "What we couldn't see"),
          leftOut.length
            ? h("p", {}, `Not shown separately on this page, so left out of the score: ${leftOut.join(", ")}.`)
            : null,
          unknown.length ? h("p", { class: "rr-fine" }, `Treated as unknown: ${unknown.join(", ")}.`) : null
        )
      );
    }

    const t = score.model && score.model.test;
    parts.push(
      h("footer", { class: "rr-foot" },
        h("p", {}, score.disclaimer ||
          "An automated estimate from the listing's text and details. It is not proof that a listing is a ghost job."),
        h("p", { class: "rr-fine" },
          `Model: ${(score.model && score.model.name) || "unknown"}`,
          t ? ` · on held-out listings it caught ${Math.round(t.recall * 100)}% of high-risk listings, and ` +
              `${Math.round(t.precision * 100)}% of its flags were correct (PR-AUC ${t.pr_auc.toFixed(2)})` : "")
      )
    );

    return h("div", { class: `rr-report rr-band-${v.color}` }, parts);
  }

  function bar(v) {
    return h("div", { class: "rr-bar", "aria-hidden": "true" },
      v.threshold != null
        ? h("div", { class: "rr-bar-range", style: `left:${v.threshold * 100}%;width:${(1 - v.threshold) * 100}%` })
        : null,
      h("div", { class: "rr-bar-fill", style: `width:${Math.max(v.risk * 100, 1)}%` })
    );
  }

  function reason(r) {
    const raises = r.direction === "raises";
    return h("li", { class: raises ? "rr-raises" : "rr-lowers" },
      h("span", { class: "rr-dir" }, raises ? "▲ Raises the risk" : "▼ Lowers the risk"),
      h("p", { class: "rr-reason-text" }, r.text)
    );
  }

  self.RealRoleReport = { render, h };
})();
