function FairnessTable({ metrics = [] }) {
  return (
    <section className="glass-panel rounded-2xl p-5">
      <h3 className="font-heading text-lg font-semibold">Fairness Metrics Breakdown</h3>

      {!metrics.length ? (
        <p className="mt-3 text-sm text-slate-600">No metric records available yet.</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-2 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-3 py-2">Metric</th>
                <th className="px-3 py-2">Group A</th>
                <th className="px-3 py-2">Group B</th>
                <th className="px-3 py-2">Disparity Score</th>
                <th className="px-3 py-2">Severity</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((metric) => (
                <tr key={metric.id} className="rounded-xl bg-white/80">
                  <td className="px-3 py-2 font-medium text-fair-ink">{metric.metric_name}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-700">{metric.group_a}</td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-700">{metric.group_b}</td>
                  <td className="px-3 py-2 font-mono">{Number(metric.disparity_score || 0).toFixed(4)}</td>
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
