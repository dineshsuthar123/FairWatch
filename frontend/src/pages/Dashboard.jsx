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
import DriftChart from "../components/DriftChart";
import ExplainerPanel from "../components/ExplainerPanel";
import FairnessTable from "../components/FairnessTable";
import ChatPanel from "../components/ChatPanel";
import DecisionCard from "../components/DecisionCard";
import InterceptionFlow from "../components/InterceptionFlow";
import BeforeAfter from "../components/BeforeAfter";
import { getSystemStatus } from "../utils/status";

const METRICS = [
  "Demographic Parity Difference",
  "Equal Opportunity Difference",
  "Disparate Impact Ratio",
  "False Positive Rate Gap",
];

const formatMetricValue = (metricName, value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return "n/a";
  return metricName === "Disparate Impact Ratio" ? numeric.toFixed(2) : numeric.toFixed(3);
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
  const [scenario, setScenario] = useState("Loan Approval");

  const refreshDashboard = useCallback(async () => {
    if (!selectedModelId) return;
    setIsLoading(true);
    try {
      const [reports, unresolvedAlerts] = await Promise.all([
        getReports(selectedModelId),
        getAlerts(selectedModelId),
      ]);
      let latest = null;
      if (reports.length > 0) {
        try { latest = await getLatestReport(selectedModelId); } 
        catch (error) { if (error?.response?.status !== 404) throw error; }
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
    const timer = setInterval(refreshDashboard, 2000);
    return () => clearInterval(timer);
  }, [refreshDashboard]);

  const liveWindowMetrics = latestReport?.live_window_metrics || [];
  const decisionSummary = latestReport?.decision_summary || null;
  const featureContributions = latestReport?.feature_contributions || { top_contributing_features: [], proxy_warnings: [] };
  const fixSuggestions = latestReport?.fix_suggestions || { fixes: [], immediate_action: "" };
  
  const currentStatus = useMemo(() => {
    const dp = liveWindowMetrics.find(m => m.metric_name === "Demographic Parity Difference")?.value || 0;
    const eo = liveWindowMetrics.find(m => m.metric_name === "Equal Opportunity Difference")?.value || 0;
    const di = liveWindowMetrics.find(m => m.metric_name === "Disparate Impact Ratio")?.value || 1;
    return getSystemStatus(dp, eo, di);
  }, [liveWindowMetrics]);

  const isBlocked = currentStatus === "unsafe" || currentStatus === "blocked";
  const mappedStatus = isBlocked ? "blocked" : "safe";
  
  const blockedCount = reportHistory.filter(r => r.severity === "red" || r.severity === "unsafe").length || (isBlocked ? 1 : 0);

  const handleRegenerate = async () => {
    if (!selectedModelId) return;
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
    if (!selectedModelId) return;
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
    if (!selectedModelId) return;
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
      <div className="bento-panel p-10 text-center max-w-lg mx-auto mt-20">
        <h2 className="font-heading text-2xl font-bold text-slate-800">Workspace Empty</h2>
      </div>
    );
  }

  // Calculate Avg Bias Metric safely
  const avgBiasValue = liveWindowMetrics.length 
    ? (liveWindowMetrics.reduce((sum, m) => sum + Math.abs(Number(m.value)), 0) / liveWindowMetrics.length).toFixed(3)
    : "0.000";

  return (
    <div className="pb-16 space-y-6">
      
      {/* 1. Teal Command Center Hero Card */}
      <div className="w-full bg-[#0F9D58] rounded-[24px] overflow-hidden shadow-lg shadow-emerald-200/50 p-6 flex flex-col md:flex-row items-center justify-between text-white border border-emerald-400/20">
        <div className="flex items-center space-x-4 mb-4 md:mb-0">
          <div className="h-14 w-14 rounded-2xl bg-white/20 flex items-center justify-center backdrop-blur-sm border border-white/20">
             <svg className="w-7 h-7 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
             </svg>
          </div>
          <div>
            <h2 className="text-2xl font-black tracking-tight leading-tight">FairWatch Command Center</h2>
            <p className="text-emerald-100 text-sm font-medium">Real-time AI monitoring & predictive analytics</p>
          </div>
        </div>
        
        <div className="flex items-center divide-x divide-emerald-400/30">
          <div className="px-6 flex flex-col items-center">
            <span className="text-3xl font-black">{models.length}</span>
            <span className="text-[10px] text-emerald-100 uppercase tracking-widest font-bold mt-1">Connected Models</span>
          </div>
          <div className="px-6 flex flex-col items-center">
            <span className="flex items-center space-x-2 text-xl font-black">
              <svg className="w-6 h-6 text-emerald-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{isBlocked ? 'Blocked' : 'Active'}</span>
            </span>
            <span className="text-[10px] text-emerald-100 uppercase tracking-widest font-bold mt-1">System Status</span>
          </div>
          <div className="px-6 flex flex-col items-center">
            <span className="text-3xl font-black">{avgBiasValue}</span>
            <span className="text-[10px] text-emerald-100 uppercase tracking-widest font-bold mt-1">Avg Bias Risk</span>
          </div>
        </div>
      </div>

      {/* Control Panel Bento */}
      <div className="elite-panel p-4 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center space-x-3 text-sm font-bold text-slate-700">
          <span className="bg-emerald-50 text-emerald-600 px-3 py-1 rounded-lg">Active Model</span>
          <select className="bg-transparent border-none outline-none cursor-pointer" value={selectedModelId ?? ""} onChange={(e) => onModelChange(Number(e.target.value))} disabled={loadingModels}>
            {models.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <div className="w-px h-6 bg-slate-200"></div>
          <span className="bg-slate-50 px-3 py-1 rounded-lg text-slate-500">Scenario</span>
          <select className="bg-transparent border-none outline-none cursor-pointer text-slate-600" value={scenario} onChange={(e) => setScenario(e.target.value)}>
             <option value="Loan Approval">Loan Approval</option>
             <option value="Hiring">Hiring</option>
             <option value="Healthcare">Healthcare</option>
          </select>
        </div>
        
        <div className="flex items-center space-x-3">
          <button className="bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-100 rounded-xl px-4 py-2 text-sm font-bold transition disabled:opacity-50" onClick={handleInjectBias} disabled={!selectedModelId || isInjecting || isLoading}>
            Inject Bias
          </button>
          <button className="bg-slate-50 text-slate-600 hover:bg-slate-100 border border-slate-200 rounded-xl px-4 py-2 text-sm font-bold transition disabled:opacity-50" onClick={handleResetDemo} disabled={!selectedModelId || isResetting || isLoading}>
            Reset
          </button>
        </div>
      </div>

      {/* Grid Layout for Main Content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        
        {/* Left Column (2/3 width) */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Decision Status Bento */}
            <div className="elite-panel p-6">
              <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Latest Decision</h3>
              <DecisionCard 
                decision_type={scenario}
                user_name={
                  scenario === "Hiring" ? "Candidate #2104" : 
                  scenario === "Healthcare" ? "Patient #849" : 
                  "Applicant #8492"
                }
                status={mappedStatus}
                reason={
                  decisionSummary?.reason || 
                  (scenario === "Hiring" ? "Bias detected in resume screening parameters" :
                   scenario === "Healthcare" ? "Bias detected in clinical risk grouping" :
                   "Bias detected in scoring parameters")
                }
              />
            </div>
            
            {/* Interception Flow Bento */}
            <div className="elite-panel p-6">
              <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Pipeline Status</h3>
              <InterceptionFlow status={mappedStatus} />
            </div>
          </div>

          <div className="elite-panel p-6">
             <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Intervention Impact</h3>
             <BeforeAfter status={mappedStatus} />
          </div>

          {/* Drift Graph Bento */}
          <div className="elite-panel p-6">
             <div className="flex items-center justify-between mb-4">
               <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest">Digital Twin Simulation (Drift)</h3>
               <span className="text-[10px] font-bold bg-emerald-50 text-emerald-600 px-2 py-1 rounded-md uppercase tracking-wider">Live</span>
             </div>
             <div className="w-full h-[350px] relative">
               {isBlocked && (
                 <div className="absolute top-1/4 right-1/4 z-20 flex items-center animate-bounce">
                    <div className="bg-red-500 text-white text-xs font-black px-3 py-1.5 rounded-lg shadow-lg border border-red-400 whitespace-nowrap">
                       Risk detected → Decision Blocked!
                    </div>
                    <div className="w-0 h-0 border-t-8 border-t-transparent border-l-[12px] border-l-red-500 border-b-8 border-b-transparent ml-[-2px]"></div>
                 </div>
               )}
               <DriftChart reports={reportHistory} />
             </div>
          </div>
        </div>

        {/* Right Column (1/3 width) */}
        <div className="xl:col-span-1 flex flex-col gap-6">
          
          {/* Fairness Status Bento */}
          <div className={`elite-panel p-6 border-t-4 ${isBlocked ? "border-t-red-500" : "border-t-[#0F9D58]"}`}>
             <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-2">Network Health</h3>
             <h2 className="text-2xl font-black text-slate-800 flex items-center gap-2 mb-4">
               {isBlocked ? <span className="text-red-500">Critical Bias Detected</span> : <span className="text-[#0F9D58]">System Optimal</span>}
             </h2>
             <div className="flex flex-col gap-3">
                {liveWindowMetrics.map(m => (
                  <div key={m.metric_name} className="flex justify-between items-center bg-slate-50 p-2.5 rounded-xl border border-slate-100">
                    <span className="text-xs font-semibold text-slate-600">{m.metric_name.replace("Difference", "").replace("Ratio", "")}</span>
                    <span className="text-sm font-bold text-slate-800">{formatMetricValue(m.metric_name, m.value)}</span>
                  </div>
                ))}
             </div>
          </div>

          <div className="elite-panel p-6 flex-1 min-h-[400px]">
             <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-4">Fairness Copilot</h3>
             <ChatPanel selectedModelId={selectedModelId} />
          </div>

        </div>
      </div>
      
    </div>
  );
}

export default Dashboard;
