const BANNER_STYLES = {
  green: {
    className: "border-fair-green/30 bg-emerald-100 text-emerald-900",
    message: "All systems fair — no bias detected",
  },
  yellow: {
    className: "border-fair-yellow/40 bg-amber-100 text-amber-900",
    message: "Warning: Bias drift detected in sensitive attributes. Monitor closely.",
  },
  red: {
    className: "border-fair-red/40 bg-rose-100 text-rose-900",
    message: "Critical: Model is actively discriminating against protected groups. Immediate review required.",
  },
};

function AlertBanner({ severity = "green", message = "" }) {
  const activeStyle = BANNER_STYLES[severity] || BANNER_STYLES.green;

  return (
    <div className={`rounded-2xl border px-4 py-3 text-sm font-semibold ${activeStyle.className}`}>
      {message || activeStyle.message}
    </div>
  );
}

export default AlertBanner;
