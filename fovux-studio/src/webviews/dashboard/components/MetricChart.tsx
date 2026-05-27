import type { CSSProperties, JSX } from "react";

const CHART_WIDTH = 320;
const CHART_HEIGHT = 180;
const CHART_PADDING = 28;
const CHART_INNER_WIDTH = CHART_WIDTH - CHART_PADDING * 2;
const CHART_INNER_HEIGHT = CHART_HEIGHT - CHART_PADDING * 2;
const GRID_LINE_COUNT = 4;
const SINGLE_POINT_OFFSET = 6;

/** A single epoch/value point in a dashboard metric series. */
export interface ChartPoint {
  x: number;
  y: number;
}

/** One named metric line rendered by the dashboard chart. */
export interface ChartSeries {
  label: string;
  color: string;
  points: ChartPoint[];
}

/** Props accepted by the dashboard metric chart. */
export interface MetricChartProps {
  title: string;
  series: ChartSeries[];
  emptyMessage: string;
}

/** Render an SVG line chart for one or more run metric series. */
export function MetricChart(props: MetricChartProps): JSX.Element {
  const { title, series, emptyMessage } = props;

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h3 style={titleStyle}>{title}</h3>
        <span style={badgeStyle}>{series.length} series</span>
      </header>
      {series.length ? (
        <>
          <ChartSvg title={title} series={series} />
          <ChartLegend series={series} />
        </>
      ) : (
        <p style={emptyStyle}>{emptyMessage}</p>
      )}
    </section>
  );
}

function ChartSvg(props: { title: string; series: ChartSeries[] }): JSX.Element {
  const { title, series } = props;
  const domain = getDomain(series);

  return (
    <svg viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`} role="img" aria-label={title}>
      <rect width={CHART_WIDTH} height={CHART_HEIGHT} rx="10" style={plotBackgroundStyle} />
      {buildGridLines(domain.minY, domain.maxY).map((line) => (
        <g key={line.value}>
          <line
            x1={CHART_PADDING}
            x2={CHART_WIDTH - CHART_PADDING}
            y1={line.y}
            y2={line.y}
            style={gridLineStyle}
          />
          <text x={CHART_PADDING - 8} y={line.y + 4} textAnchor="end" style={axisTextStyle}>
            {formatAxisValue(line.value)}
          </text>
        </g>
      ))}
      {series.map((item) => (
        <polyline
          key={item.label}
          points={toPolylinePoints(item.points, domain)}
          fill="none"
          stroke={item.color}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </svg>
  );
}

function ChartLegend(props: { series: ChartSeries[] }): JSX.Element {
  return (
    <div style={legendStyle}>
      {props.series.map((item) => (
        <span key={item.label} style={legendItemStyle}>
          <span style={{ ...legendSwatchStyle, background: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  );
}

function getDomain(series: ChartSeries[]): {
  maxX: number;
  maxY: number;
  minX: number;
  minY: number;
} {
  const points = series.flatMap((item) => item.points);
  const xValues = points.map((point) => point.x);
  const yValues = points.map((point) => point.y);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);

  return {
    minX: Math.min(...xValues),
    maxX: Math.max(...xValues),
    minY: minY === maxY ? minY - SINGLE_POINT_OFFSET : minY,
    maxY: minY === maxY ? maxY + SINGLE_POINT_OFFSET : maxY,
  };
}

function buildGridLines(minY: number, maxY: number): { value: number; y: number }[] {
  return Array.from({ length: GRID_LINE_COUNT + 1 }, (_item, index) => {
    const ratio = index / GRID_LINE_COUNT;
    const value = maxY - (maxY - minY) * ratio;
    return {
      value,
      y: CHART_PADDING + CHART_INNER_HEIGHT * ratio,
    };
  });
}

function toPolylinePoints(
  points: ChartPoint[],
  domain: { maxX: number; maxY: number; minX: number; minY: number }
): string {
  return points
    .map(
      (point) =>
        `${scaleX(point.x, domain.minX, domain.maxX)},${scaleY(point.y, domain.minY, domain.maxY)}`
    )
    .join(" ");
}

function scaleX(value: number, min: number, max: number): number {
  const ratio = (value - min) / safeSpan(min, max);
  return CHART_PADDING + ratio * CHART_INNER_WIDTH;
}

function scaleY(value: number, min: number, max: number): number {
  const ratio = (value - min) / safeSpan(min, max);
  return CHART_HEIGHT - CHART_PADDING - ratio * CHART_INNER_HEIGHT;
}

function safeSpan(min: number, max: number): number {
  return max === min ? 1 : max - min;
}

function formatAxisValue(value: number): string {
  return Math.abs(value) >= 10 ? value.toFixed(0) : value.toFixed(2);
}

const panelStyle: CSSProperties = {
  display: "grid",
  gap: "12px",
  padding: "16px",
  borderRadius: "16px",
  border: "1px solid var(--vscode-panel-border)",
  background: "var(--vscode-sideBar-background)",
};

const headerStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  gap: "12px",
  alignItems: "center",
};

const titleStyle: CSSProperties = {
  margin: 0,
};

const badgeStyle: CSSProperties = {
  color: "var(--vscode-descriptionForeground)",
  fontSize: "12px",
};

const emptyStyle: CSSProperties = {
  margin: 0,
  color: "var(--vscode-descriptionForeground)",
};

const plotBackgroundStyle: CSSProperties = {
  fill: "var(--vscode-editor-background)",
  stroke: "var(--vscode-panel-border)",
};

const gridLineStyle: CSSProperties = {
  stroke: "var(--vscode-panel-border)",
  strokeWidth: 1,
};

const axisTextStyle: CSSProperties = {
  fill: "var(--vscode-descriptionForeground)",
  fontSize: "10px",
};

const legendStyle: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "10px",
};

const legendItemStyle: CSSProperties = {
  display: "inline-flex",
  gap: "6px",
  alignItems: "center",
  fontSize: "12px",
};

const legendSwatchStyle: CSSProperties = {
  width: "10px",
  height: "10px",
  borderRadius: "999px",
};
