const riskDistance = (metricName, score) => {
  const safeScore = Number.isFinite(Number(score)) ? Number(score) : 0;
  if (metricName === "Disparate Impact Ratio") {
    return Math.abs(1 - safeScore);
  }
  return Math.abs(safeScore);
};

const toneForScore = (score, severity) => {
  const normalizedSeverity = String(severity || "").toLowerCase();
  if (normalizedSeverity === "red") {
    return {
      badge: "bg-rose-100 text-rose-900",
      bar: "bg-rose-600",
      label: "Red",
    };
  }

  if (normalizedSeverity === "yellow") {
    return {
      badge: "bg-amber-100 text-amber-900",
      bar: "bg-amber-500",
      label: "Yellow",
    };
  }

  if (normalizedSeverity === "green") {
    return {
      badge: "bg-emerald-100 text-emerald-900",
      bar: "bg-emerald-600",
      label: "Green",
    };
  }

  if (score < 0.1) {
    return {
      badge: "bg-emerald-100 text-emerald-900",
      bar: "bg-emerald-600",
      label: "Green",
    };
  }

  if (score <= 0.2) {
    return {
      badge: "bg-amber-100 text-amber-900",
      bar: "bg-amber-500",
      label: "Yellow",
    };
  }

  return {
    badge: "bg-rose-100 text-rose-900",
    bar: "bg-rose-600",
    label: "Red",
  };
};

function BiasScoreCard({ metricName, score = 0, severity = "" }) {
  const safeScore = Number.isFinite(Number(score)) ? Number(score) : 0;
  const riskScore = riskDistance(metricName, safeScore);
  const tone = toneForScore(riskScore, severity);
  const percentage = Math.max(0, Math.min(100, riskScore * 100));

  return (
    <article className="bg-transparent rounded-2xl border border-slate-200/70 p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-800">{metricName}</h3>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone.badge}`}>{tone.label}</span>
      </div>

      <p className="mt-4 font-mono text-3xl font-bold tracking-tight text-fair-ink">{safeScore.toFixed(3)}</p>

      <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`metric-bar h-full rounded-full ${tone.bar}`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percentage}
          aria-label={`${metricName} disparity score`}
        />
      </div>
    </article>
  );
}

export default BiasScoreCard;
