import type { RequiredLimits } from '../lib/limits';
import { hoursFigure } from '../lib/format';
import {
  buildPolylinePoints,
  DUTY_LINE_WIDTH,
  gridFrame,
  hourLabelLayout,
  remarkAnchor,
  remarkLeader,
  rowLayout,
  tickLines,
  tickMarks,
  totalHours,
  totalsColumn,
} from '../lib/logGrid';
import type { DayTotals, Remark, Segment } from '../types';
import './LogGrid.css';

export interface LogGridProps {
  segments: Segment[];
  totals: DayTotals;
  remarks: Remark[];
  limits: RequiredLimits;
}

/** The 24-hour, four-row duty status grid with its totals column and remarks band. Every coordinate comes from
 * lib/logGrid; this component only places what it is given. */
export function LogGrid({ segments, totals, remarks, limits }: LogGridProps) {
  const frame = gridFrame();
  const rows = rowLayout();
  const ticks = tickMarks(limits);
  const totalsLayout = totalsColumn();

  return (
    <svg
      className="log-grid"
      viewBox={frame.viewBox}
      preserveAspectRatio="xMidYMin meet"
      role="img"
      aria-labelledby="log-grid-title"
    >
      <title id="log-grid-title">Duty status grid, midnight to midnight</title>

      <rect className="log-grid__hour-band" {...frame.hourBand} />
      <g className="log-grid__hour-labels">
        {ticks.map((tick) => {
          if (!tick.label) {
            return null;
          }
          const label = hourLabelLayout(tick);
          return (
            <text key={tick.x} textAnchor={label.anchor} data-hour-label={tick.label}>
              {label.lines.map((line) => (
                <tspan key={line.text} x={line.x} y={line.y}>
                  {line.text}
                </tspan>
              ))}
            </text>
          );
        })}
        {totalsLayout.heading.map((line) => (
          <text key={line.text} x={line.x} y={line.y} textAnchor="middle">
            {line.text}
          </text>
        ))}
      </g>

      <g className="log-grid__rows">
        {rows.map((row) => (
          <g key={row.status} data-row={row.status}>
            <text className="log-grid__row-label">
              {row.labelLines.map((line) => (
                <tspan key={line.text} x={line.x} y={line.y}>
                  {line.text}
                </tspan>
              ))}
            </text>
            <line className="log-grid__rule" {...row.rule} />
          </g>
        ))}
        <rect className="log-grid__outline" {...frame.grid} />
      </g>

      <g className="log-grid__ticks">
        {ticks.map((tick) => (
          <g key={tick.x} className={`log-grid__tick log-grid__tick--${tick.size}`} data-tick={tick.size}>
            {tickLines(tick).map((line) => (
              <line key={line.y1} {...line} />
            ))}
          </g>
        ))}
      </g>

      <polyline
        className="log-grid__duty-line"
        points={buildPolylinePoints(segments, limits)}
        strokeWidth={DUTY_LINE_WIDTH}
      />

      <g className="log-grid__totals">
        {rows.map((row) => (
          <g key={row.status} data-total={row.status}>
            <text x={row.total.x} y={row.total.y} textAnchor="middle">
              {hoursFigure(totals[row.status])}
            </text>
            <line className="log-grid__rule" {...row.total.rule} />
          </g>
        ))}
        <g data-total="sum">
          <text x={totalsLayout.sum.x} y={totalsLayout.sum.y} textAnchor="middle">
            {`=${hoursFigure(totalHours(totals))}`}
          </text>
          <line className="log-grid__rule log-grid__rule--double" {...totalsLayout.sum.rule} />
        </g>
      </g>

      <g className="log-grid__remarks">
        <text className="log-grid__remarks-heading" x={frame.remarksHeading.x} y={frame.remarksHeading.y}>
          {frame.remarksHeading.text}
        </text>
        {remarks.map((remark, index) => {
          const anchor = remarkAnchor(remark.at_min, limits);
          return (
            <g key={`${remark.at_min}-${index}`} data-remark={remark.at_min}>
              <line className="log-grid__leader" {...remarkLeader(remark.at_min, limits)} />
              {remark.location && (
                <text x={anchor.x} y={anchor.y} transform={anchor.transform} textAnchor="end" dominantBaseline="central">
                  {remark.location}
                </text>
              )}
            </g>
          );
        })}
      </g>
    </svg>
  );
}
