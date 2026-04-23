import React from "react";

function InterceptionFlow({ status }) {
  const isBlocked = status === "blocked";

  return (
    <div className="w-full flex flex-col items-center justify-center h-full">
      <div className="flex flex-row items-center justify-center gap-2 md:gap-4 w-full">
        
        {/* Node 1: AI Model */}
        <div className="flex flex-col items-center w-20">
          <div className="w-12 h-12 md:w-16 md:h-16 rounded-2xl bg-indigo-50 flex items-center justify-center border border-indigo-100 shadow-sm z-10 transition-transform hover:scale-105">
            <span className="text-xl md:text-2xl">🤖</span>
          </div>
          <span className="mt-2 font-bold text-slate-700 text-[10px] uppercase text-center">AI Model</span>
        </div>

        {/* Arrow */}
        <div className="flex flex-col items-center text-slate-300 md:-mt-6">
          <span className="text-lg font-black">→</span>
        </div>

        {/* Node 2: FairWatch */}
        <div className="flex flex-col items-center w-24">
          <div className="relative flex justify-center items-center">
            <div className={`absolute inset-0 rounded-full animate-ping opacity-20 ${isBlocked ? "bg-red-500" : "bg-emerald-500"}`}></div>
            <div className={`w-16 h-16 md:w-20 md:h-20 rounded-full flex items-center justify-center border-4 shadow-md z-10 relative transition-transform hover:scale-105 ${isBlocked ? "bg-red-50 border-red-500 text-red-600" : "bg-emerald-50 border-emerald-500 text-emerald-600"}`}>
              <span className="text-2xl md:text-3xl">🔥</span>
            </div>
          </div>
          <span className="mt-2 font-black text-slate-900 text-xs uppercase text-center">FairWatch</span>
        </div>

        {/* Arrow */}
        <div className="flex flex-col items-center text-slate-300 md:-mt-6">
          <span className="text-lg font-black">→</span>
        </div>

        {/* Node 3: Result */}
        <div className="flex flex-col items-center w-20 relative">
          <div className={`w-12 h-12 md:w-16 md:h-16 rounded-2xl flex items-center justify-center border shadow-sm z-10 transition-all ${isBlocked ? "bg-red-50 border-red-300" : "bg-emerald-50 border-emerald-300"}`}>
             <span className="text-xl md:text-2xl">{isBlocked ? "🛑" : "💳"}</span>
          </div>
          <span className={`mt-2 font-bold text-[10px] uppercase text-center ${isBlocked ? "text-red-600" : "text-emerald-700"}`}>
             {isBlocked ? "BLOCKED" : "DELIVERED"}
          </span>
          
          {/* Conditional Dropdown for Blocked */}
          {isBlocked && (
            <div className="absolute top-full mt-1 w-full text-center animate-reveal-up">
              <span className="text-red-400 text-sm block leading-none">↓</span>
              <p className="text-[8px] font-black uppercase tracking-widest text-red-600 bg-red-100 px-1 py-0.5 rounded inline-block mt-0.5">Quarantine</p>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

export default InterceptionFlow;
