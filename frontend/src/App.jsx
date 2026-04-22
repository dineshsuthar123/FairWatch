import { useEffect, useMemo, useState } from "react";

import { getModels, withApiError } from "./api/client";
import Alerts from "./pages/Alerts";
import Dashboard from "./pages/Dashboard";
import Upload from "./pages/Upload";

const NAV_ITEMS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "upload", label: "Upload" },
  { id: "alerts", label: "Alerts" },
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
    <div className="relative min-h-screen overflow-x-hidden px-4 pb-12 pt-8 text-fair-ink sm:px-8 lg:px-14">
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-70" aria-hidden="true" />

      <header className="glass-panel soft-shine rounded-3xl border border-slate-200/70 p-5 sm:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="inline-flex items-center rounded-full bg-emerald-100 px-3 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-emerald-800">
              Live Fairness Ops
            </p>
            <h1 className="mt-3 font-heading text-3xl font-black sm:text-4xl">FairWatch</h1>
            <p className="mt-2 max-w-xl text-sm text-slate-600">
              Real-time AI bias monitoring after deployment.
            </p>
          </div>

          <nav className="rounded-2xl border border-slate-200 bg-white/60 p-2 shadow-sm">
            <div className="flex flex-wrap gap-2">
            {NAV_ITEMS.map((item) => {
              const active = activePage === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                    active
                      ? "bg-gradient-to-r from-slate-900 to-slate-700 text-white shadow-lg"
                      : "bg-white/80 text-fair-ink hover:bg-white"
                  }`}
                  onClick={() => setActivePage(item.id)}
                >
                  {item.label}
                </button>
              );
            })}
            </div>
          </nav>
        </div>
      </header>

      {errorMessage && (
        <div className="mt-4 rounded-2xl border border-fair-red/30 bg-fair-red/10 px-4 py-3 text-sm text-fair-red">
          {errorMessage}
        </div>
      )}

      <main className="mt-6">
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
      </main>
    </div>
  );
}

export default App;
