import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  getAlerts,
  getLatestReport,
  getReports,
  injectDemoBias,
  regenerateLatestExplanation,
  resetDemo,
  withApiError,
} from "../api/client";
import AlertBanner from "../components/AlertBanner";
import BiasScoreCard from "../components/BiasScoreCard";
import DriftChart from "../components/DriftChart";
import ExplainerPanel from "../components/ExplainerPanel";
import FairnessTable from "../components/FairnessTable";

const METRICS = [
  "Demographic Parity Difference",
  "Equal Opportunity Difference",
  "Disparate Impact Ratio",
  "False Positive Rate Gap",
];

const PRIORITY_STYLES = {
  critical: "bg-rose-100 text-rose-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-amber-100 text-amber-800",
};

const FIX_TYPE_ICONS = {
  reweight: "⚖️",
  remove_proxy: "🚫",
  threshold_tuning: "🎚️",
};

function Dashboard({ models, selectedModelId, onModelChange, loadingModels }) {
  const [reportHistory, setReportHistory] = useState([]);
  const [latestReport, setLatestReport] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isInjecting, setIsInjecting] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const refreshDashboard = useCallback(async () => {
    if (!selectedModelId) {
      setLatestReport(null);
      setReportHistory([]);
      setAlerts([]);
      return;
    }

    setIsLoading(true);
    try {
      const [reports, unresolvedAlerts] = await Promise.all([
        getReports(selectedModelId),
        getAlerts(selectedModelId),
      ]);

      let latest = null;
      try {
        latest = await getLatestReport(selectedModelId);
      } catch (error) {
        if (error?.response?.status !== 404) {
          throw error;
        }
      }

      setReportHistory(reports);
      setAlerts(unresolvedAlerts);
      setLatestReport(latest);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to refresh dashboard data."));
    } finally {
      setIsLoading(false);
    }
  }, [selectedModelId]);

  useEffect(() => {
    refreshDashboard();
    const timer = setInterval(refreshDashboard, 30000);
    return () => clearInterval(timer);
  }, [refreshDashboard]);

  const metricSummaries = useMemo(() => {
    const scoreMap = {
      "Demographic Parity Difference": {
        score: 0,
        meaning: "No interpretation available yet.",
      },
      "Equal Opportunity Difference": {
        score: 0,
        meaning: "No interpretation available yet.",
      },
      "Disparate Impact Ratio": {
        score: 0,
        meaning: "No interpretation available yet.",
      },
      "False Positive Rate Gap": {
        score: 0,
        meaning: "No interpretation available yet.",
      },
    };

    if (!latestReport?.metrics) {
      return scoreMap;
    }

    latestReport.metrics.forEach((metric) => {
      const name = metric.metric_name;
      const score = Number(metric.disparity_score || 0);
      if (name in scoreMap && score >= scoreMap[name].score) {
        scoreMap[name] = {
          score,
          meaning: metric.metric_meaning || "No interpretation available yet.",
        };
      }
    });

    return scoreMap;
  }, [latestReport]);

  const featureContributions = latestReport?.feature_contributions || {
    top_contributing_features: [],
    proxy_warnings: [],
  };

  const warningByFeature = useMemo(() => {
    const map = {};
    (featureContributions.proxy_warnings || []).forEach((warning) => {
      const split = String(warning).split(" correlates ", 2);
      if (split.length === 2) {
        map[split[0]] = warning;
      }
    });
    return map;
  }, [featureContributions]);

  const fixSuggestions = latestReport?.fix_suggestions || { fixes: [], immediate_action: "" };

  const topAlert = alerts.length ? alerts[0] : null;
  const bannerSeverity = topAlert?.severity || latestReport?.severity || "green";
  const bannerMessage = topAlert?.message || "";

  const handleRegenerate = async () => {
    if (!selectedModelId) {
      return;
    }

    setIsRegenerating(true);
    try {
      const regenerated = await regenerateLatestExplanation(selectedModelId);
      setLatestReport(regenerated);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to regenerate explanation."));
    } finally {
      setIsRegenerating(false);
    }
  };

  const handleInjectBias = async () => {
    if (!selectedModelId) {
      return;
    }

    setIsInjecting(true);
    try {
      await injectDemoBias(selectedModelId);
      await refreshDashboard();
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to inject bias for demo."));
    } finally {
      setIsInjecting(false);
    }
  };

  const handleResetDemo = async () => {
    if (!selectedModelId) {
      return;
    }

    setIsResetting(true);
    try {
      await resetDemo(selectedModelId);
      await refreshDashboard();
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to reset demo state."));
    } finally {
      setIsResetting(false);
    }
  };

  if (!models.length && !loadingModels) {
    return (
      <section className="glass-panel rounded-2xl p-6">
        <h2 className="font-heading text-xl font-bold">No Models Yet</h2>
        <p className="mt-2 text-sm text-slate-600">
          Register a model from the Upload page to start real-time fairness monitoring.
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div className="glass-panel rounded-2xl p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            className="rounded-xl bg-rose-600 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleInjectBias}
            disabled={!selectedModelId || isInjecting || isLoading}
          >
            {isInjecting ? "Injecting..." : "🔴 Inject Bias"}
          </button>

          <button
            type="button"
            className="rounded-xl bg-slate-700 px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleResetDemo}
            disabled={!selectedModelId || isResetting || isLoading}
          >
            {isResetting ? "Resetting..." : "🔄 Reset Demo"}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-500">Demo controls — simulate real-time bias injection</p>
      </div>

      <div className="glass-panel flex flex-col gap-3 rounded-2xl p-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.15em] text-slate-500">Monitoring Dashboard</p>
          <h2 className="font-heading text-2xl font-bold">Near Real-Time Batch Monitoring (window: last 100 predictions)</h2>
        </div>

        <div className="w-full sm:w-80">
          <label htmlFor="model-select" className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
            Model Selector
          </label>
          <select
            id="model-select"
            className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
            value={selectedModelId ?? ""}
            onChange={(event) => onModelChange(Number(event.target.value))}
            disabled={loadingModels}
          >
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <AlertBanner severity={bannerSeverity} message={bannerMessage} />

      {errorMessage && (
        <div className="rounded-xl border border-fair-red/30 bg-fair-red/10 px-4 py-2 text-sm text-fair-red">{errorMessage}</div>
      )}

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {METRICS.map((metricName) => {
          const item = metricSummaries[metricName];
          return (
            <div key={metricName} className="space-y-2">
              <BiasScoreCard metricName={metricName} score={item.score} />
              <p className="px-1 text-xs text-slate-500">{item.meaning}</p>
            </div>
          );
        })}
      </div>

      {isLoading && <p className="text-sm text-slate-600">Refreshing monitoring data...</p>}

      <DriftChart reports={reportHistory} />

      <section className="glass-panel rounded-2xl p-5">
        <h3 className="font-heading text-lg font-semibold">Root Cause Analysis</h3>

        {!featureContributions.top_contributing_features?.length ? (
          <p className="mt-3 text-sm text-slate-600">No feature contribution data available yet.</p>
        ) : (
          <>
            <div className="mt-4 h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={featureContributions.top_contributing_features}
                  layout="vertical"
                  margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" dataKey="contribution_pct" unit="%" />
                  <YAxis type="category" dataKey="feature" width={120} />
                  <Tooltip
                    formatter={(value) => [`${Number(value).toFixed(2)}%`, "Contribution"]}
                    content={({ active, payload }) => {
                      if (!active || !payload || !payload.length) {
                        return null;
                      }
                      const data = payload[0].payload;
                      const warning = warningByFeature[data.feature];
                      return (
                        <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs shadow-lg">
                          <p className="font-semibold text-slate-800">{data.feature}</p>
                          <p className="mt-1 text-slate-700">Contribution: {Number(data.contribution_pct).toFixed(2)}%</p>
                          <p className={`mt-1 ${warning ? "text-rose-700" : "text-slate-500"}`}>
                            {warning || "No high proxy correlation detected."}
                          </p>
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="contribution_pct" radius={[0, 8, 8, 0]}>
                    {featureContributions.top_contributing_features.map((entry) => (
                      <Cell key={entry.feature} fill={entry.proxy_risk ? "#b42318" : "#2563eb"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>

            {!!featureContributions.proxy_warnings?.length && (
              <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-rose-700">Proxy Warnings</p>
                <ul className="mt-2 list-disc space-y-1 pl-4 text-sm text-rose-800">
                  {featureContributions.proxy_warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </section>

      <ExplainerPanel
        explanation={latestReport?.explanation}
        timestamp={latestReport?.timestamp}
        onRegenerate={handleRegenerate}
        isRegenerating={isRegenerating}
      />

      <section className="glass-panel rounded-2xl p-5">
        <h3 className="font-heading text-lg font-semibold">Recommended Actions</h3>

        {!fixSuggestions.fixes?.length ? (
          <p className="mt-3 text-sm text-slate-600">No fix suggestions available yet.</p>
        ) : (
          <div className="mt-4 space-y-3">
            {fixSuggestions.fixes.map((fix, index) => (
              <article key={`${fix.type}-${index}`} className="rounded-xl border border-slate-200 bg-white/80 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-lg" aria-hidden="true">{FIX_TYPE_ICONS[fix.type] || "🛠️"}</span>
                  <span
                    className={`rounded-full px-2 py-1 text-xs font-semibold uppercase ${
                      PRIORITY_STYLES[String(fix.priority || "").toLowerCase()] || "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {fix.priority || "unspecified"}
                  </span>
                </div>
                <p className="mt-2 text-sm font-semibold text-fair-ink">{fix.action}</p>
                <p className="mt-1 text-sm text-slate-500">{fix.impact}</p>
              </article>
            ))}
          </div>
        )}

        {fixSuggestions.immediate_action && (
          <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <span className="font-semibold">Immediate Action: </span>
            {fixSuggestions.immediate_action}
          </div>
        )}
      </section>

      <FairnessTable metrics={latestReport?.metrics || []} />
    </section>
  );
}

export default Dashboard;
