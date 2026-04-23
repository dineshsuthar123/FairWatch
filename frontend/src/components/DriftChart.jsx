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

const toTime = (timestamp) => new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

function buildChartData(reports) {
  const bucket = {};

  reports.forEach((report) => {
    if (!report?.timestamp) {
      return;
    }

    const timeLabel = toTime(report.timestamp);
    const group = report.group_b || "unknown";
    const score = Number(report.disparity_score || 0);

    if (!bucket[timeLabel]) {
      bucket[timeLabel] = { timeLabel, timestamp: new Date(report.timestamp).getTime() };
    }

    bucket[timeLabel][group] = Math.max(score, Number(bucket[timeLabel][group] || 0));
  });

  return Object.values(bucket).sort((a, b) => a.timestamp - b.timestamp);
}

function DriftChart({ reports = [] }) {
  const chartData = useMemo(() => buildChartData(reports), [reports]);

  const groups = useMemo(() => {
    const keys = new Set();
    chartData.forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (key !== "timeLabel" && key !== "timestamp") {
          keys.add(key);
        }
      });
    });
    return Array.from(keys);
  }, [chartData]);

  if (!chartData.length || !groups.length) {
    return (
      <section className="bg-transparent rounded-2xl p-5">
        <h3 className="font-heading text-lg font-semibold">Bias Drift Over Time</h3>
        <p className="mt-2 text-sm text-slate-600">No bias report history available yet.</p>
      </section>
    );
  }

  return (
    <section className="bg-transparent rounded-2xl p-5 flex flex-col h-full w-full">
      <div>
        <h3 className="font-heading text-lg font-semibold">Bias Drift Over Time</h3>
        <p className="mt-1 text-sm text-slate-600">Threshold line at 0.10 indicates elevated fairness risk.</p>
      </div>

      <div className="mt-4 flex-1 min-h-0 min-w-0 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="4 4" stroke="#d3dde7" />
            <XAxis dataKey="timeLabel" tick={{ fontSize: 11 }} />
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
                  isAnimationActive={false}
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
