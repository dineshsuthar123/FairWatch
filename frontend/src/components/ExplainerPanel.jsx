function ExplainerPanel({ explanation, timestamp, onRegenerate, isRegenerating = false }) {
  return (
    <section className="glass-panel rounded-2xl p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="font-heading text-lg font-semibold">AI Fairness Auditor Report</h3>
          <p className="mt-1 text-xs font-mono text-slate-500">
            {timestamp ? `Generated at ${new Date(timestamp).toLocaleString()}` : "No report timestamp available"}
          </p>
        </div>

        <button
          type="button"
          className="rounded-xl bg-fair-ink px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
          onClick={onRegenerate}
          disabled={isRegenerating}
        >
          {isRegenerating ? "Regenerating..." : "Regenerate Explanation"}
        </button>
      </div>

      <div className="mt-4 rounded-xl border border-slate-200 bg-white/80 p-4 text-sm leading-relaxed text-slate-700">
        {explanation || "No explanation available yet. Submit predictions to generate the first AI fairness report."}
      </div>
    </section>
  );
}

export default ExplainerPanel;
