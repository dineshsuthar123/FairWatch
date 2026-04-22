import { useMemo } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const THRESHOLD = 0.1;
const COLORS = ["#147d64", "#0369a1", "#d97706", "#8b5cf6", "#0f766e"];

const toDay = (timestamp) => new Date(timestamp).toISOString().slice(0, 10);

function buildChartData(reports) {
  const bucket = {};

  reports.forEach((report) => {
    if (!report?.timestamp) {
      return;
    }

    const day = toDay(report.timestamp);
    const group = report.group_b || "unknown";
    const score = Number(report.disparity_score || 0);

    if (!bucket[day]) {
      bucket[day] = { day };
    }

    bucket[day][group] = Math.max(score, Number(bucket[day][group] || 0));
  });

  return Object.values(bucket).sort((a, b) => new Date(a.day) - new Date(b.day));
}

function DriftChart({ reports = [] }) {
  const chartData = useMemo(() => buildChartData(reports), [reports]);

  const groups = useMemo(() => {
    const keys = new Set();
    chartData.forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (key !== "day") {
          keys.add(key);
        }
      });
    });
    return Array.from(keys);
  }, [chartData]);

  if (!chartData.length || !groups.length) {
    return (
      <section className="glass-panel rounded-2xl p-5">
        <h3 className="font-heading text-lg font-semibold">Bias Drift Over Time</h3>
        <p className="mt-2 text-sm text-slate-600">No bias report history available yet.</p>
      </section>
    );
  }

  return (
    <section className="glass-panel rounded-2xl p-5">
      <h3 className="font-heading text-lg font-semibold">Bias Drift Over Time</h3>
      <p className="mt-1 text-sm text-slate-600">Threshold line at 0.10 indicates elevated fairness risk.</p>

      <div className="mt-4 h-[320px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="4 4" stroke="#d3dde7" />
            <XAxis dataKey="day" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} domain={[0, 0.5]} />
            <Tooltip />
            <Legend />
            <ReferenceLine y={THRESHOLD} stroke="#b42318" strokeDasharray="8 4" />

            {groups.map((group, index) => {
              const crossed = chartData.some((row) => Number(row[group] || 0) > THRESHOLD);

              return (
                <Line
                  key={group}
                  type="monotone"
                  dataKey={group}
                  stroke={crossed ? "#b42318" : COLORS[index % COLORS.length]}
                  strokeWidth={crossed ? 3 : 2}
                  className={crossed ? "danger-line" : ""}
                  dot={false}
                  isAnimationActive
                />
              );
            })}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

export default DriftChart;
