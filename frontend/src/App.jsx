import { useEffect, useMemo, useState } from "react";

import { getModels, withApiError } from "./api/client";
import Alerts from "./pages/Alerts";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";
import Settings from "./pages/Settings";
import Integrations from "./pages/Integrations";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard", sub: "Overview & monitoring", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" },
  { id: "upload", label: "Model Registry", sub: "Manage AI models", icon: "M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" },
  { id: "alerts", label: "Governance Alerts", sub: "Fairness tracking", icon: "M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" },
  { id: "integrations", label: "Integrations", sub: "Connect tools", icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" },
  { id: "settings", label: "Settings", sub: "Configuration", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" },
];

function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [models, setModels] = useState([]);
  const [selectedModelId, setSelectedModelId] = useState(null);
  const [loadingModels, setLoadingModels] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  const loadModels = async (resetSelection = false) => {
    setLoadingModels(true);
    try {
      const fetchedModels = await getModels();
      setModels(fetchedModels);

      if (!fetchedModels.length) {
        setSelectedModelId(null);
      } else if (resetSelection || !fetchedModels.some((model) => model.id === selectedModelId)) {
        setSelectedModelId(fetchedModels[0].id);
      }

      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to load models."));
    } finally {
      setLoadingModels(false);
    }
  };

  useEffect(() => {
    loadModels(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedModel = useMemo(
    () => models.find((model) => model.id === selectedModelId) || null,
    [models, selectedModelId],
  );

  return (
    <div className="flex min-h-screen font-body text-slate-800 bg-[var(--bg-1)]">
      {/* Sidebar Navigation */}
      <aside className="w-72 bg-white flex flex-col justify-between sticky top-0 h-screen shadow-[4px_0_24px_rgba(0,0,0,0.02)] hidden lg:flex border-r border-emerald-50">
        <div className="p-6">
          {/* Logo Section */}
          <div className="flex items-center space-x-3 mb-10 mt-2">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#0F9D58] shadow-md shadow-emerald-200">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
              </svg>
            </div>
            <div>
              <h1 className="font-heading text-xl font-bold tracking-tight text-slate-900 leading-tight">
                FairWatch
              </h1>
              <span className="text-[11px] font-medium text-slate-500 flex items-center gap-1">
                <span className="text-amber-500">✦</span> Digital Twin Platform
              </span>
            </div>
          </div>
          
          <div className="mb-4 pl-4">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
              Navigation
            </span>
          </div>

          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => {
              const active = activePage === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`w-full flex items-center space-x-4 px-4 py-3 rounded-[24px] transition-all ${
                    active
                      ? "bg-[#0F9D58] text-white shadow-md shadow-emerald-200"
                      : "text-slate-500 hover:bg-emerald-50 hover:text-[#0F9D58]"
                  }`}
                  onClick={() => setActivePage(item.id)}
                >
                  <svg className={`w-5 h-5 ${active ? "text-white" : "text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={item.icon} />
                  </svg>
                  <div className="text-left flex flex-col">
                    <span className={`text-sm font-bold ${active ? "text-white" : "text-slate-700"}`}>
                      {item.label}
                    </span>
                    <span className={`text-[11px] ${active ? "text-emerald-100" : "text-slate-400"}`}>
                      {item.sub}
                    </span>
                  </div>
                </button>
              );
            })}
          </nav>
        </div>
        
        <div className="p-6">
          <div className="bg-emerald-50 rounded-3xl p-4 flex items-center space-x-3 border border-emerald-100/50">
            <div className="h-8 w-8 rounded-xl bg-[#0F9D58] flex items-center justify-center shadow-sm">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <p className="text-sm font-bold text-slate-800 leading-tight">System Active</p>
              <p className="text-[11px] text-slate-500">Digital Twin Online</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Pane */}
      <main className="flex-1 w-full max-h-screen overflow-y-auto flex flex-col">
        
        {/* Top Header */}
        <header className="w-full bg-[var(--bg-1)] px-8 py-6 flex items-center justify-between sticky top-0 z-50">
          <div className="flex items-center space-x-4">
            <h2 className="text-xl font-bold text-slate-800">FairWatch Management System</h2>
            <div className="flex items-center space-x-1.5 bg-[#0F9D58] px-2.5 py-1 rounded-full shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-200 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-white"></span>
              </span>
              <span className="text-xs font-bold text-white tracking-wide">Live</span>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2 bg-white px-4 py-2 rounded-xl border border-slate-200/60 shadow-sm text-sm font-medium text-slate-600">
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.243-4.243a8 8 0 1111.314 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <span>Bangalore, India</span>
            </div>
            <div className="h-10 w-10 rounded-full bg-[#0F9D58] flex items-center justify-center text-white font-bold shadow-md shadow-emerald-200 border-2 border-white">
              AD
            </div>
          </div>
        </header>

        {/* Mobile Nav Top Bar (Fallback for small screens) */}
        <div className="lg:hidden flex justify-between items-center px-4 py-4 bg-white border-b border-slate-200">
          <h1 className="font-heading text-xl font-bold text-[#0F9D58]">FairWatch.</h1>
          <select 
            className="text-sm bg-slate-50 border border-slate-200 rounded-lg px-2 py-1"
            value={activePage}
            onChange={(e) => setActivePage(e.target.value)}
          >
            {NAV_ITEMS.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
          </select>
        </div>

        <div className="w-full px-8 pb-8">
          {errorMessage && (
            <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 font-medium shadow-sm">
              {errorMessage}
            </div>
          )}

          {activePage === "dashboard" && (
            <Dashboard
              models={models}
              selectedModel={selectedModel}
              selectedModelId={selectedModelId}
              onModelChange={setSelectedModelId}
              loadingModels={loadingModels}
            />
          )}

          {activePage === "upload" && (
            <Upload
              onModelRegistered={async (modelId) => {
                await loadModels(false);
                setSelectedModelId(modelId);
                setActivePage("dashboard");
              }}
            />
          )}

          {activePage === "alerts" && (
            <Alerts
              models={models}
              selectedModelId={selectedModelId}
              onModelChange={setSelectedModelId}
            />
          )}

          {activePage === "integrations" && <Integrations />}
          {activePage === "settings" && <Settings />}
        </div>
      </main>
    </div>
  );
}

export default App;
