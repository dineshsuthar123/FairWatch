import React from "react";

function DecisionBlockCard({ status, reason, affected_groups }) {
  if (status !== "unsafe") return null;

  const affectedText =
    affected_groups && affected_groups.length > 0
      ? affected_groups.join(", ")
      : "Unknown";

  return (
    <div className="w-full bg-red-500 rounded-xl p-6 text-white shadow-xl mb-6">
      <div className="flex items-center gap-4 border-b border-red-400/50 pb-4 mb-4">
        <div className="text-4xl">❌</div>
        <h2 className="text-3xl font-black tracking-tight uppercase">Decision Blocked</h2>
      </div>
      <div className="space-y-2">
        <p className="text-lg font-medium">
          <span className="font-bold uppercase tracking-wider text-red-200 text-sm block mb-1">Reason:</span> 
          {reason || "Automated guardrail triggered due to high disparity."}
        </p>
        <p className="text-lg font-medium">
          <span className="font-bold uppercase tracking-wider text-red-200 text-sm block mt-4 mb-1">Affected Group:</span> 
          {affectedText}
        </p>
        <p className="text-lg font-bold text-white mt-4 bg-red-600/50 inline-block px-3 py-1 rounded">
          Action: Prevented from reaching user
        </p>
      </div>
    </div>
  );
}

export default DecisionBlockCard;
