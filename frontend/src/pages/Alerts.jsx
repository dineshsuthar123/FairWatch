import { useEffect, useMemo, useState } from "react";

import { getAlerts, resolveAlert, withApiError } from "../api/client";

function Alerts({ models }) {
  const [modelFilter, setModelFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [alerts, setAlerts] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [resolvingId, setResolvingId] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const refreshAlerts = async () => {
    if (!models.length) {
      setAlerts([]);
      return;
    }

    setIsLoading(true);
    try {
      const responses = await Promise.all(
        models.map(async (model) => {
          const unresolved = await getAlerts(model.id);
          return unresolved.map((alert) => ({
            ...alert,
            model_name: alert.model_name || model.name,
          }));
        }),
      );

      const merged = responses
        .flat()
        .sort((first, second) => new Date(second.triggered_at) - new Date(first.triggered_at));

      setAlerts(merged);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to fetch alerts."));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshAlerts();
    const timer = setInterval(refreshAlerts, 30000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [models]);

  const visibleAlerts = useMemo(
    () =>
      alerts.filter((alert) => {
        const modelMatch =
          modelFilter === "all" ? true : String(alert.model_id) === String(modelFilter);
        const severityMatch = severityFilter === "all" ? true : alert.severity === severityFilter;
        return modelMatch && severityMatch;
      }),
    [alerts, modelFilter, severityFilter],
  );

  const handleResolve = async (alertId) => {
    setResolvingId(alertId);
    try {
      await resolveAlert(alertId);
      await refreshAlerts();
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to resolve alert."));
    } finally {
      setResolvingId(null);
    }
  };

  return (
    <section className="space-y-4">
      <div className="bento-panel bg-white rounded-2xl p-6">
        <h2 className="font-heading text-2xl font-bold">Active Alerts</h2>
        <p className="mt-1 text-sm text-slate-600">
          Review unresolved fairness alerts and resolve them after mitigation.
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="alert-model-filter">
              Filter by Model
            </label>
            <select
              id="alert-model-filter"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              value={modelFilter}
              onChange={(event) => setModelFilter(event.target.value)}
            >
              <option value="all">All Models</option>
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="severity-filter">
              Filter by Severity
            </label>
            <select
              id="severity-filter"
              className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
            >
              <option value="all">All Severities</option>
              <option value="red">Red</option>
              <option value="yellow">Yellow</option>
              <option value="green">Green</option>
            </select>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="rounded-xl border border-fair-red/30 bg-fair-red/10 px-4 py-3 text-sm text-fair-red">{errorMessage}</div>
      )}

      <div className="bento-panel bg-white overflow-x-auto rounded-2xl p-4">
        {isLoading && <p className="px-2 py-3 text-sm text-slate-600">Refreshing alerts...</p>}

        {!isLoading && !visibleAlerts.length ? (
          <p className="px-2 py-3 text-sm text-slate-600">No unresolved alerts match this filter.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-2 py-3">Model</th>
                <th className="px-2 py-3">Severity</th>
                <th className="px-2 py-3">Message</th>
                <th className="px-2 py-3">Timestamp</th>
                <th className="px-2 py-3">Action</th>
              </tr>
            </thead>
            <tbody>
              {visibleAlerts.map((alert) => (
                <tr key={alert.id} className="border-b border-slate-100 align-top">
                  <td className="px-2 py-3 font-semibold text-fair-ink">{alert.model_name || `Model ${alert.model_id}`}</td>
                  <td className="px-2 py-3">
                    <span
                      className={`rounded-full px-2 py-1 text-xs font-semibold uppercase ${
                        alert.severity === "red"
                          ? "bg-rose-100 text-rose-700"
                          : alert.severity === "yellow"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-emerald-100 text-emerald-700"
                      }`}
                    >
                      {alert.severity}
                    </span>
                  </td>
                  <td className="px-2 py-3 text-slate-700">{alert.message}</td>
                  <td className="px-2 py-3 text-xs font-mono text-slate-600">
                    {new Date(alert.triggered_at).toLocaleString()}
                  </td>
                  <td className="px-2 py-3">
                    <button
                      type="button"
                      className="rounded-lg bg-fair-ink px-3 py-1.5 text-xs font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
                      onClick={() => handleResolve(alert.id)}
                      disabled={resolvingId === alert.id}
                    >
                      {resolvingId === alert.id ? "Resolving..." : "Resolve"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

export default Alerts;
