function FairnessTable({ metrics = [] }) {
  return (
    <section className="bg-transparent rounded-2xl p-5">
      <h3 className="font-heading text-lg font-semibold">Fairness Metrics Breakdown</h3>

      {!metrics.length ? (
        <p className="mt-3 text-sm text-slate-600">No metric records available yet.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-2 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2">Metric</th>
                <th className="px-3 py-2">Metric Type</th>
                <th className="px-3 py-2">Group A</th>
                <th className="px-3 py-2">Group B</th>
                <th className="px-3 py-2">Value</th>
                <th className="px-3 py-2">Severity</th>
                <th className="px-3 py-2">Confidence</th>
                <th className="px-3 py-2">Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric, index) => (
                <tr
                  key={`${metric.metric_name}-${metric.group_a}-${metric.group_b}-${metric.metric_type || metric.metric_scope || "live_window"}-${index}`}
                  className={`rounded-xl ${
                    String(metric.confidence || "").toLowerCase() === "low"
                      ? "bg-amber-50/90"
                      : "bg-white/80"
                  }`}
                >
                  <td className="px-3 py-2 font-medium text-fair-ink">{metric.metric_name}</td>
                  <td className="px-3 py-2">
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-[11px] font-semibold uppercase text-slate-700">
                      {metric.metric_type || metric.metric_scope || "live_window"}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-700">{metric.group_a}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-700">{metric.group_b}</td>
                  <td className="px-3 py-2 font-mono">{Number(metric.value ?? metric.disparity_score ?? 0).toFixed(4)}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold uppercase ${
                        metric.severity === "red"
                          ? "bg-rose-100 text-rose-700"
                          : metric.severity === "yellow"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {metric.severity}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold uppercase ${
                        String(metric.confidence || "").toLowerCase() === "high"
                          ? "bg-emerald-100 text-emerald-700"
                          : String(metric.confidence || "").toLowerCase() === "medium"
                            ? "bg-sky-100 text-sky-700"
                            : "bg-amber-100 text-amber-700"
                      }`}
                    >
                      {metric.confidence || "low"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-700">
                    {metric.interpretation || metric.metric_meaning || "No interpretation available yet."}
                    {metric.confidence_warning && (
                      <p className="mt-1 font-semibold text-amber-700">{metric.confidence_warning}</p>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default FairnessTable;
