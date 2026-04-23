function Integrations() {
  const integrationList = [
    { name: "AWS SageMaker", category: "ML Hosting", status: "Connected", desc: "Automated bias monitoring for SageMaker endpoint predictions." },
    { name: "Databricks", category: "Data Lakehouse", status: "Available", desc: "Sync Delta Tables directly into the FairWatch evaluation engine." },
    { name: "Snowflake", category: "Data Warehouse", status: "Available", desc: "Native Secure Data Sharing pipeline for bulk historical audits." },
    { name: "Slack", category: "Alerting", status: "Connected", desc: "Push critical bias drift notifications to your #mlops channel." },
    { name: "PagerDuty", category: "Incident Response", status: "Needs Config", desc: "Trigger on-call incidents when model guardrails are breached." },
    { name: "Apache Kafka", category: "Event Stream", status: "Available", desc: "Ingest high-throughput prediction streams in real time." },
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto animate-rise">
      <div className="flex flex-col pb-4 border-b border-slate-200">
        <h2 className="font-heading text-3xl font-extrabold tracking-tight text-slate-900">
          Enterprise Integrations
        </h2>
        <p className="text-sm text-slate-500 mt-1 font-medium">Connect FairWatch to your existing ML ecosystem.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {integrationList.map((item) => (
          <div key={item.name} className="bento-panel flex flex-col p-6 hover:-translate-y-1 transition duration-200 cursor-default">
            <div className="flex justify-between items-start mb-4">
              <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center text-xl font-black text-slate-400">
                {item.name.charAt(0)}
              </div>
              <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-1 rounded-md ${
                item.status === 'Connected' ? 'bg-emerald-100 text-emerald-700' :
                item.status === 'Needs Config' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'
              }`}>
                {item.status}
              </span>
            </div>
            <h3 className="font-heading font-bold text-lg text-slate-900 mb-1">{item.name}</h3>
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">{item.category}</p>
            <p className="text-sm text-slate-600 flex-1 leading-relaxed mb-6">{item.desc}</p>
            <button className="w-full py-2 rounded-lg border border-slate-200 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition cursor-pointer">
              {item.status === "Connected" ? "Configure Settings" : "Enable Integration"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Integrations;
