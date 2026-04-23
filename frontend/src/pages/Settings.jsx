function Settings() {
  return (
    <div className="space-y-6 max-w-4xl mx-auto animate-rise">
      <div className="flex flex-col pb-4 border-b border-slate-200">
        <h2 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">
          Organization Settings
        </h2>
        <p className="text-sm text-slate-500 mt-1 font-medium">Manage AI policies, guardrails, and access control.</p>
      </div>

      <div className="space-y-6">
        {/* Guardrail Policies */}
        <div className="bento-panel p-6">
          <h3 className="font-heading font-bold text-lg text-slate-900 mb-4">Automated Guardrail Policies</h3>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between py-3 border-b border-slate-100">
              <div>
                <p className="text-sm font-bold text-slate-800">Auto-Remediation Execution</p>
                <p className="text-xs text-slate-500 mt-1 max-w-md">Allow the system to automatically apply reweighting pipelines immediately when disparity is flagged.</p>
              </div>
              <div className="w-12 h-6 bg-emerald-500 rounded-full relative cursor-pointer shadow-inner">
                <div className="absolute right-1 top-1 bg-white w-4 h-4 rounded-full shadow-sm"></div>
              </div>
            </div>

            <div className="flex items-center justify-between py-3 border-b border-slate-100">
              <div>
                <p className="text-sm font-bold text-slate-800">Enforce Minimum Confidence Interval</p>
                <p className="text-xs text-slate-500 mt-1 max-w-md">Only trigger governance alerts if anomalous metric statistical confidence exceeds 95%.</p>
              </div>
              <div className="w-12 h-6 bg-slate-200 rounded-full relative cursor-pointer shadow-inner">
                <div className="absolute left-1 top-1 bg-white w-4 h-4 rounded-full shadow-sm"></div>
              </div>
            </div>
            
            <div className="py-3">
              <label className="text-sm font-bold text-slate-800 flex justify-between">
                Global Disparate Impact Tolerance
                <span className="text-emerald-600 font-mono">0.80</span>
              </label>
              <p className="text-xs text-slate-500 mt-1 mb-3">The threshold ratio (commonly the four-fifths rule) at which bias constitutes a critical incident.</p>
              <input type="range" className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer" min="0.5" max="1" step="0.05" defaultValue="0.8" />
            </div>
          </div>
        </div>

        {/* API Access */}
        <div className="bento-panel p-6">
          <h3 className="font-heading font-bold text-lg text-slate-900 mb-1">Developer API Keys</h3>
          <p className="text-xs text-slate-500 mb-4">Integrate your models programmatically via the FairWatch Python SDK.</p>
          
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 font-mono text-sm flex items-center justify-between">
            <span className="text-slate-500">fw_live_9d8f72a........................e23</span>
            <button className="text-xs font-bold text-slate-600 hover:text-slate-900 bg-white border border-slate-200 px-3 py-1 rounded shadow-sm">Copy</button>
          </div>
          <button className="mt-4 px-4 py-2 border border-emerald-500 text-emerald-700 text-sm font-bold rounded-lg hover:bg-emerald-50 transition cursor-pointer">Generate New Key</button>
        </div>
        
      </div>
    </div>
  );
}

export default Settings;
