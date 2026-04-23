const SECTION_HEADINGS = [
  { label: "WHAT IS HAPPENING", key: "what_is_happening" },
  { label: "WHY IT IS HAPPENING", key: "why_it_is_happening" },
  { label: "REAL WORLD IMPACT", key: "real_world_impact" },
  { label: "IMMEDIATE ACTION", key: "recommended_action" },
];

function severityBadge(severity) {
  if (severity === "red") {
    return {
      label: "Unsafe",
      className: "border-rose-200 bg-rose-50 text-rose-700",
    };
  }

  if (severity === "yellow") {
    return {
      label: "Risky",
      className: "border-amber-200 bg-amber-50 text-amber-700",
    };
  }

  return {
    label: "Safe",
    className: "border-emerald-200 bg-emerald-50 text-emerald-700",
  };
}

function parseStructuredExplanation(explanation) {
  if (!explanation) {
    return null;
  }

  if (typeof explanation === "object") {
    return explanation;
  }

  try {
    const parsed = JSON.parse(explanation);
    if (parsed && typeof parsed === "object") {
      return parsed;
    }
  } catch {
    return null;
  }

  return null;
}

function parseLegacyExplanation(explanation) {
  if (!explanation || typeof explanation !== "string") {
    return null;
  }

  const normalized = explanation.replace(/\r\n/g, "\n").trim();
  const upper = normalized.toUpperCase();
  const matches = SECTION_HEADINGS.map((section) => ({
    ...section,
    index: upper.indexOf(section.label),
  }))
    .filter((section) => section.index !== -1)
    .sort((left, right) => left.index - right.index);

  if (!matches.length) {
    return null;
  }

  const parsed = {
    headline: "AI Fairness Auditor Report",
    what_is_happening: "",
    why_it_is_happening: "",
    affected_groups: [],
    real_world_impact: "",
    recommended_action: "",
  };

  matches.forEach((section, index) => {
    const start = section.index + section.label.length;
    const end = index + 1 < matches.length ? matches[index + 1].index : normalized.length;
    const content = normalized
      .slice(start, end)
      .replace(/^:\s*/, "")
      .trim();

    parsed[section.key] = content;
  });

  return parsed;
}

function buildAffectedGroups(metrics) {
  const rows = Array.isArray(metrics) ? metrics : [];
  const ranked = rows
    .slice()
    .sort((left, right) => {
      const rank = { green: 1, yellow: 2, red: 3 };
      const leftScore = rank[String(left?.severity || "").toLowerCase()] || 0;
      const rightScore = rank[String(right?.severity || "").toLowerCase()] || 0;
      if (leftScore !== rightScore) {
        return rightScore - leftScore;
      }
      return Number(right?.disparity_score || 0) - Number(left?.disparity_score || 0);
    });

  const riskyRows = ranked.filter((metric) => ["red", "yellow"].includes(String(metric?.severity || "").toLowerCase()));
  const source = riskyRows.length ? riskyRows : ranked;

  return [...new Set(source.map((metric) => metric?.group_b).filter(Boolean))].slice(0, 6);
}

function buildFallbackExplanation({ severity, metrics, fixSuggestions }) {
  const rank = { green: 1, yellow: 2, red: 3 };
  const sortedMetrics = (Array.isArray(metrics) ? metrics : []).slice().sort((left, right) => {
    const leftSeverity = rank[String(left?.severity || "").toLowerCase()] || 0;
    const rightSeverity = rank[String(right?.severity || "").toLowerCase()] || 0;
    if (leftSeverity !== rightSeverity) {
      return rightSeverity - leftSeverity;
    }
    return Number(right?.disparity_score || 0) - Number(left?.disparity_score || 0);
  });
  const topMetric = sortedMetrics[0];
  const affectedGroups = buildAffectedGroups(metrics);
  const recommendedAction =
    fixSuggestions?.immediate_action ||
    fixSuggestions?.fixes?.[0]?.action ||
    "Review the flagged groups and fix the main bias drivers before deployment.";

  if (!topMetric) {
    return {
      headline: "No AI fairness report available yet.",
      what_is_happening: "Submit predictions to generate the first fairness report.",
      why_it_is_happening: "Root-cause details will appear after monitoring data is available.",
      affected_groups: [],
      real_world_impact: "No live fairness impact can be summarized yet.",
      recommended_action: recommendedAction,
    };
  }

  const topScore = Number(topMetric.disparity_score || 0).toFixed(4);
  const topGroup = topMetric.group_b || "the compared group";

  return {
    headline:
      severity === "red"
        ? "Unsafe to deploy."
        : severity === "yellow"
          ? "Fairness risk needs action before deployment."
          : "No critical fairness issue detected.",
    what_is_happening: `${topMetric.metric_name} is ${topScore} in the latest report, with ${topGroup} showing the clearest gap.`,
    why_it_is_happening: "Use the root-cause analysis below to review the strongest feature drivers behind this gap.",
    affected_groups: affectedGroups,
    real_world_impact:
      severity === "red"
        ? "The current model can lead to unfair decisions for the affected groups and should not be deployed."
        : "The current report should be reviewed before wider deployment decisions are made.",
    recommended_action: recommendedAction,
  };
}

function mergeExplanation(primary, fallback) {
  return {
    headline: primary?.headline || fallback.headline,
    what_is_happening: primary?.what_is_happening || fallback.what_is_happening,
    why_it_is_happening: primary?.why_it_is_happening || fallback.why_it_is_happening,
    affected_groups:
      Array.isArray(primary?.affected_groups) && primary.affected_groups.length
        ? primary.affected_groups
        : fallback.affected_groups,
    real_world_impact: primary?.real_world_impact || fallback.real_world_impact,
    recommended_action: primary?.recommended_action || fallback.recommended_action,
  };
}

function ExplainerPanel({
  explanation,
  timestamp,
  severity,
  metrics,
  fixSuggestions,
  onRegenerate,
  isRegenerating = false,
}) {
  const fallbackExplanation = buildFallbackExplanation({ severity, metrics, fixSuggestions });
  const parsedExplanation =
    parseStructuredExplanation(explanation) ||
    parseLegacyExplanation(explanation) ||
    fallbackExplanation;
  const report = mergeExplanation(parsedExplanation, fallbackExplanation);
  const badge = severityBadge(severity);

  return (
    <section className="bg-transparent rounded-2xl p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="font-heading text-lg font-semibold">AI Fairness Auditor Report</h3>
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-wide ${badge.className}`}>
              {badge.label}
            </span>
          </div>
          <p className="mt-1 font-mono text-xs text-slate-500">
            {timestamp ? `Generated at ${new Date(timestamp).toLocaleString()}` : "No report timestamp available"}
          </p>
        </div>

        <button
          type="button"
          className="rounded-xl bg-fair-ink px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onRegenerate}
          disabled={isRegenerating}
        >
          {isRegenerating ? "Regenerating..." : "Regenerate Report"}
        </button>
      </div>

      <div className="mt-4 rounded-2xl border border-slate-200 bg-white/90 p-5 shadow-sm">
        <div className="rounded-2xl border border-slate-200/80 bg-slate-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Executive Summary</p>
          <p className="mt-2 text-base font-semibold text-slate-900">{report.headline}</p>
          <p className="mt-2 text-sm leading-relaxed text-slate-700">{report.what_is_happening}</p>
        </div>

        {!!report.affected_groups?.length && (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Affected Groups</span>
            {report.affected_groups.map((group) => (
              <span key={group} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                {group}
              </span>
            ))}
          </div>
        )}

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <article className="rounded-2xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Why It Is Happening</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{report.why_it_is_happening}</p>
          </article>

          <article className="rounded-2xl border border-slate-200 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Real-World Impact</p>
            <p className="mt-2 text-sm leading-relaxed text-slate-700">{report.real_world_impact}</p>
          </article>
        </div>

        <article className="mt-4 rounded-2xl border border-blue-200 bg-blue-50/80 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">Recommended Action</p>
          <p className="mt-2 text-sm font-medium leading-relaxed text-blue-900">{report.recommended_action}</p>
        </article>
      </div>
    </section>
  );
}

export default ExplainerPanel;
