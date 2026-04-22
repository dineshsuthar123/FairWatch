const toneForScore = (score) => {
  if (score < 0.05) {
    return {
      badge: "bg-emerald-100 text-emerald-900",
      bar: "bg-emerald-600",
      label: "Green",
    };
  }

  if (score <= 0.1) {
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

function BiasScoreCard({ metricName, score = 0 }) {
  const safeScore = Number.isFinite(Number(score)) ? Number(score) : 0;
  const tone = toneForScore(safeScore);
  const percentage = Math.max(0, Math.min(100, safeScore * 100));

  return (
    <article className="glass-panel rounded-2xl p-4">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-700">{metricName}</h3>
        <span className={`rounded-full px-2 py-1 text-xs font-semibold ${tone.badge}`}>{tone.label}</span>
      </div>

      <p className="mt-4 font-mono text-3xl font-semibold tracking-tight text-fair-ink">{safeScore.toFixed(3)}</p>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-200">
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
