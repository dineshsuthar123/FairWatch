const BANNER_STYLES = {
  green: {
    className: "border-emerald-300/80 bg-gradient-to-r from-emerald-100 to-emerald-50 text-emerald-900",
    message: "All systems fair — no bias detected",
  },
  yellow: {
    className: "border-amber-300/80 bg-gradient-to-r from-amber-100 to-amber-50 text-amber-900",
    message: "Warning: Bias drift detected in sensitive attributes. Monitor closely.",
  },
  red: {
    className: "border-rose-300/80 bg-gradient-to-r from-rose-100 to-rose-50 text-rose-900",
    message: "Critical: Model is actively discriminating against protected groups. Immediate review required.",
  },
};

function AlertBanner({ severity = "green", message = "" }) {
  const activeStyle = BANNER_STYLES[severity] || BANNER_STYLES.green;

  const icon = severity === "red" ? "⚠" : severity === "yellow" ? "!" : "✓";

  return (
    <div className={`glass-panel rounded-2xl border px-4 py-3 text-sm font-semibold shadow-sm ${activeStyle.className}`}>
      <div className="flex items-center gap-2">
        <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-white/80 text-xs font-bold">{icon}</span>
        <span>{message || activeStyle.message}</span>
      </div>
    </div>
  );
}

export default AlertBanner;
