import React, { useState } from "react";
import {
  TrendingUp,
  Sparkles,
  Award,
} from "lucide-react";
import type { PerformanceTrendPoint } from "../../types/progress";

interface PerformanceTrendsChartProps {
  trendPoints: PerformanceTrendPoint[];
  periodLabel: string;
  onNavigate: (path: string) => void;
  onViewSessionScorecard: (sessionId: string) => void;
}

export const PerformanceTrendsChart: React.FC<PerformanceTrendsChartProps> = ({
  trendPoints,
  periodLabel,
  onNavigate,
  onViewSessionScorecard,
}) => {
  const [activePointIndex, setActivePointIndex] = useState<number | null>(
    trendPoints.length > 0 ? trendPoints.length - 1 : null
  );

  if (trendPoints.length === 0) {
    return (
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-8 shadow-sm text-center">
        <div className="w-12 h-12 rounded-xl bg-neutral-100 dark:bg-neutral-800 text-neutral-400 flex items-center justify-center mx-auto mb-3">
          <TrendingUp className="w-6 h-6" />
        </div>
        <h3 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white mb-1">
          No Completed Viva Sessions in this Period
        </h3>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 max-w-md mx-auto mb-5">
          {periodLabel === "All Time"
            ? "Practice viva oral exams for your experiments to track your score progression and readiness over time."
            : `No viva sessions recorded in ${periodLabel}. Try expanding your reporting filter or take a practice viva now.`}
        </p>
        <button
          onClick={() => onNavigate("/viva-practice")}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 text-xs font-semibold hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors shadow-2xs"
        >
          <Sparkles className="w-3.5 h-3.5 text-emerald-400 dark:text-emerald-600" />
          Practice Viva Now
        </button>
      </div>
    );
  }

  // Dimensions for responsive SVG coordinate mapping
  const width = 640;
  const height = 210;
  const paddingLeft = 45;
  const paddingRight = 30;
  const paddingTop = 25;
  const paddingBottom = 35;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  // Compute coordinates
  const points = trendPoints.map((point, i) => {
    const x =
      trendPoints.length === 1
        ? paddingLeft + chartWidth / 2
        : paddingLeft + (i / (trendPoints.length - 1)) * chartWidth;

    // Y scale from 0 to 10
    const clampedScore = Math.max(0, Math.min(10, point.score));
    const y = paddingTop + (1 - clampedScore / 10) * chartHeight;

    return { ...point, x, y };
  });

  // Build SVG path
  const linePath =
    points.length === 1
      ? ""
      : points.reduce((path, pt, idx) => {
          return idx === 0 ? `M ${pt.x},${pt.y}` : `${path} L ${pt.x},${pt.y}`;
        }, "");

  // Area path for gradient background
  const areaPath =
    points.length === 1
      ? ""
      : `${linePath} L ${points[points.length - 1].x},${paddingTop + chartHeight} L ${points[0].x},${paddingTop + chartHeight} Z`;

  const activePoint = activePointIndex !== null ? points[activePointIndex] : points[points.length - 1];

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
      {/* Header and Details */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-600" />
            Viva Performance Over Time
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Chronological trendline of oral viva evaluations ({trendPoints.length} {trendPoints.length === 1 ? "session" : "sessions"} recorded)
          </p>
        </div>

        {activePoint && (
          <div className="flex items-center gap-3 p-2 px-3 rounded-xl bg-neutral-50 dark:bg-neutral-800/60 border border-neutral-200 dark:border-neutral-700 text-xs">
            <div>
              <span className="text-[10px] uppercase font-bold text-neutral-400 block">
                Selected Session
              </span>
              <span className="font-semibold text-neutral-900 dark:text-white truncate max-w-[150px] inline-block">
                {activePoint.experimentTitle}
              </span>
            </div>
            <div className="text-right pl-2 border-l border-neutral-200 dark:border-neutral-700">
              <span className="text-[10px] text-neutral-400 block">Score</span>
              <span className="font-bold text-emerald-600 dark:text-emerald-400">
                {activePoint.score.toFixed(1)}/10
              </span>
            </div>
            <button
              onClick={() => onViewSessionScorecard(activePoint.sessionId)}
              className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 hover:underline flex items-center gap-0.5 pl-1"
            >
              <Award className="w-3 h-3" /> View
            </button>
          </div>
        )}
      </div>

      {/* SVG Line Chart */}
      <div className="relative w-full overflow-x-auto select-none pt-2">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full h-auto min-w-[500px] overflow-visible"
          aria-label="Viva Performance Chart"
        >
          <defs>
            <linearGradient id="trendGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
          </defs>

          {/* Grid lines and Y-axis labels (0, 2.5, 5.0, 7.5, 10.0) */}
          {[10, 7.5, 5.0, 2.5, 0].map((val) => {
            const y = paddingTop + (1 - val / 10) * chartHeight;
            return (
              <g key={val}>
                <line
                  x1={paddingLeft}
                  y1={y}
                  x2={width - paddingRight}
                  y2={y}
                  stroke="currentColor"
                  className="text-neutral-200 dark:text-neutral-800"
                  strokeDasharray="3 3"
                />
                <text
                  x={paddingLeft - 8}
                  y={y + 3}
                  textAnchor="end"
                  className="text-[10px] fill-neutral-400 font-medium"
                >
                  {val.toFixed(1)}
                </text>
              </g>
            );
          })}

          {/* Area fill */}
          {areaPath && (
            <path d={areaPath} fill="url(#trendGradient)" />
          )}

          {/* Main Trend Line */}
          {linePath && (
            <path
              d={linePath}
              fill="none"
              stroke="#10b981"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          )}

          {/* Data Points */}
          {points.map((pt, i) => {
            const isSelected = activePointIndex === i;
            return (
              <g
                key={pt.sessionId}
                className="cursor-pointer"
                onClick={() => setActivePointIndex(i)}
              >
                {/* Invisible larger hover hit area */}
                <circle cx={pt.x} cy={pt.y} r="14" fill="transparent" />

                {/* Outer halo if active */}
                {isSelected && (
                  <circle
                    cx={pt.x}
                    cy={pt.y}
                    r="8"
                    className="fill-emerald-200/50 dark:fill-emerald-900/50 stroke-emerald-500"
                    strokeWidth="1.5"
                  />
                )}

                {/* Dot */}
                <circle
                  cx={pt.x}
                  cy={pt.y}
                  r={isSelected ? "5" : "4"}
                  className="fill-white dark:fill-neutral-900 stroke-emerald-600 dark:stroke-emerald-400"
                  strokeWidth={isSelected ? "2.5" : "2"}
                />

                {/* Score label above point */}
                <text
                  x={pt.x}
                  y={pt.y - 10}
                  textAnchor="middle"
                  className="text-[10px] font-bold fill-neutral-700 dark:fill-neutral-300"
                >
                  {pt.score.toFixed(1)}
                </text>

                {/* Date label at bottom */}
                <text
                  x={pt.x}
                  y={paddingTop + chartHeight + 18}
                  textAnchor="middle"
                  className={`text-[10px] ${
                    isSelected
                      ? "font-bold fill-neutral-900 dark:fill-white"
                      : "fill-neutral-400"
                  }`}
                >
                  {pt.dateLabel}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {trendPoints.length === 1 && (
        <p className="text-xs text-neutral-500 text-center italic pt-1">
          1 session recorded. Complete additional viva simulations to build a multi-session trendline.
        </p>
      )}
    </div>
  );
};

export default PerformanceTrendsChart;
