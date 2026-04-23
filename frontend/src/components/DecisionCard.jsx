import React from "react";

function DecisionCard({ decision_type, user_name, status, reason }) {
  const isBlocked = status === "blocked";
  const bgColor = isBlocked ? "bg-red-50" : "bg-emerald-50";
  const borderColor = isBlocked ? "border-red-200" : "border-emerald-200";
  const textColor = isBlocked ? "text-red-700" : "text-emerald-700";
  const icon = isBlocked ? "🛑" : "✅";
  const statusText = isBlocked ? "BLOCKED" : "SAFE";

  return (
    <div className="w-full flex flex-col h-full justify-between">
      <div className={`rounded-2xl border ${borderColor} ${bgColor} p-5 mb-6`}>
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-bold text-slate-500 uppercase tracking-widest">{decision_type || "Loan Approval"}</span>
          <span className={`text-xs font-black uppercase tracking-widest px-2 py-1 rounded-md ${isBlocked ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>
            {statusText}
          </span>
        </div>
        <div className="flex items-center space-x-3">
          <span className="text-3xl">{icon}</span>
          <h2 className={`text-xl font-black tracking-tight ${textColor}`}>
            {user_name || "Applicant #8492"}
          </h2>
        </div>
      </div>

      <div className="space-y-5 flex-1">
        <div>
           <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Guardrail Status</p> 
           <p className="text-sm font-bold text-slate-700 leading-snug">{reason || (isBlocked ? "Bias detected in scoring parameters" : "No systemic bias detected")}</p>
        </div>
        <div>
           <p className="text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">System Action</p> 
           <p className={`text-sm font-bold ${textColor}`}>
             {isBlocked ? "Prevented from reaching user" : "Authorized"}
           </p>
        </div>
      </div>
    </div>
  );
}

export default DecisionCard;
