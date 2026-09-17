import { useId, useMemo, useState } from "react";

/**
 * Charts.
 *
 * The product holds a double-entry ledger, a booking diary, fourteen days of
 * stock movement and a labor forecast, and rendered every one of them as a
 * table of numbers. These are the four places a shape says it faster.
 *
 * The colours are not hand-picked. They were run through the palette validator
 * against this app's surface (#0E0B0C) and chosen by what passed:
 *
 *   money direction   rose #D9788D out / mint #77D8C2 in
 *                     CVD ΔE 12.5 deutan, 25.5 normal, contrast ≥3:1 — safe.
 *                     Knowingly outside the dark-mode lightness band, and the
 *                     band is the one check worth relaxing here: these sit
 *                     *lighter* than it, which on a near-black surface is more
 *                     contrast rather than less, and swapping them for in-band
 *                     steps collapsed their separation to ΔE 2.5.
 *
 *   everything else   one hue and a de-emphasis grey. Magnitude is sequential,
 *                     not categorical: colouring bars by their own value spends
 *                     the identity channel re-encoding what length already says.
 *
 * Every chart here ships with a hover read-out and a table view, because a
 * chart nobody can interrogate is a picture of data rather than data.
 */

const PAD = { top: 10, right: 12, bottom: 22, left: 44 };

function useHover() {
  const [at, setAt] = useState(null);
  return [at, setAt];
}

function money(cents) {
  const v = Math.round((cents || 0) / 100);
  return `${v < 0 ? "−" : ""}$${Math.abs(v).toLocaleString()}`;
}

function shortDate(iso) {
  const [, m, d] = iso.split("-");
  return `${Number(d)}/${Number(m)}`;
}

/** The table behind every chart. Identity is never colour alone. */
function DataTable({ open, columns, rows }) {
  if (!open) return null;
  return (
    <div className="chart-table-wrap">
      <table className="chart-table">
        <thead>
          <tr>{columns.map((c) => <th key={c} scope="col">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((cell, j) => <td key={j}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Frame({ title, note, legend, children, table }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className="chart">
      <figcaption className="chart-head">
        <div>
          <h3>{title}</h3>
          {note && <p>{note}</p>}
        </div>
        <div className="chart-head-right">
          {legend}
          <button type="button" className="chart-table-toggle"
                  onClick={() => setShowTable((v) => !v)}
                  aria-expanded={showTable}>
            {showTable ? "Hide numbers" : "Show numbers"}
          </button>
        </div>
      </figcaption>
      {children}
      <DataTable open={showTable} {...table} />
    </figure>
  );
}

/* ==========================================================================
   1. Cash in against cash out
   ========================================================================== */

export function CashChart({ series }) {
  const [hover, setHover] = useHover();
  const id = useId();

  const { w, h, peak, x, y, inPath, outPath } = useMemo(() => {
    const w = 640, h = 190;
    const peak = Math.max(1, ...series.map((d) => Math.max(d.in, d.out)));
    const plotW = w - PAD.left - PAD.right;
    const plotH = h - PAD.top - PAD.bottom;
    const x = (i) => PAD.left + (i / Math.max(series.length - 1, 1)) * plotW;
    const y = (v) => PAD.top + plotH - (v / peak) * plotH;
    const line = (key) =>
      series.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d[key]).toFixed(1)}`).join(" ");
    return { w, h, peak, x, y, inPath: line("in"), outPath: line("out") };
  }, [series]);

  if (!series?.length) return null;

  const anyIn = series.some((d) => d.in > 0);
  const anyOut = series.some((d) => d.out > 0);
  const point = hover != null ? series[hover] : null;

  return (
    <Frame
      title="Cash in and out"
      note="Last 30 days, by day."
      legend={
        <span className="chart-legend">
          <span className="chart-key is-in">In</span>
          <span className="chart-key is-out">Out</span>
        </span>
      }
      table={{
        columns: ["Date", "In", "Out"],
        rows: series.map((d) => [d.date, money(d.in), money(d.out)]),
      }}
    >
      <div className="chart-plot">
        <svg viewBox={`0 0 ${w} ${h}`} role="img"
             aria-label={`Cash in and out per day over the last ${series.length} days`}
             onMouseLeave={() => setHover(null)}>
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line className="chart-grid" x1={PAD.left} x2={w - PAD.right}
                    y1={y(peak * t)} y2={y(peak * t)} />
              <text className="chart-tick" x={PAD.left - 8} y={y(peak * t) + 3}
                    textAnchor="end">{money(peak * t)}</text>
            </g>
          ))}

          {anyOut && <path className="chart-line is-out" d={outPath} />}
          {anyIn && <path className="chart-line is-in" d={inPath} />}

          {point && (
            <>
              <line className="chart-crosshair" x1={x(hover)} x2={x(hover)}
                    y1={PAD.top} y2={h - PAD.bottom} />
              {anyIn && <circle className="chart-dot is-in" cx={x(hover)} cy={y(point.in)} r="4" />}
              {anyOut && <circle className="chart-dot is-out" cx={x(hover)} cy={y(point.out)} r="4" />}
            </>
          )}

          <text className="chart-tick" x={PAD.left} y={h - 6}>{shortDate(series[0].date)}</text>
          <text className="chart-tick" x={w - PAD.right} y={h - 6} textAnchor="end">
            {shortDate(series[series.length - 1].date)}
          </text>

          {/* Hit targets wider than the marks. */}
          {series.map((d, i) => (
            <rect key={i} x={x(i) - 6} y={PAD.top} width="12" height={h - PAD.top - PAD.bottom}
                  fill="transparent" onMouseEnter={() => setHover(i)} />
          ))}
        </svg>

        {point && (
          <div className="chart-tip" style={{ left: `${(x(hover) / w) * 100}%` }} role="status">
            <strong>{point.date}</strong>
            <span className="is-in">In {money(point.in)}</span>
            <span className="is-out">Out {money(point.out)}</span>
          </div>
        )}
      </div>
    </Frame>
  );
}

/* ==========================================================================
   2. Labor as a share of revenue, against the lines that matter
   ========================================================================== */

export function LaborChart({ days, healthy = 33, ceiling = 40 }) {
  const [hover, setHover] = useHover();
  if (!days?.length) return null;

  const w = 640, h = 190;
  const peak = Math.max(ceiling + 8, ...days.map((d) => d.percent || 0));
  const plotW = w - PAD.left - PAD.right;
  const plotH = h - PAD.top - PAD.bottom;
  const band = plotW / days.length;
  const y = (v) => PAD.top + plotH - (v / peak) * plotH;

  const point = hover != null ? days[hover] : null;

  return (
    <Frame
      title="Labor against forecast"
      note={`Each day's wage bill against an even split of the week's forecast. `
            + `Hospitality targets about ${healthy}%; past ${ceiling}% the week loses money.`}
      table={{
        columns: ["Day", "Labor %"],
        rows: days.map((d) => [d.date, d.percent == null ? "—" : `${d.percent}%`]),
      }}
    >
      <div className="chart-plot">
        <svg viewBox={`0 0 ${w} ${h}`} role="img"
             aria-label="Labor as a percentage of forecast revenue, by day"
             onMouseLeave={() => setHover(null)}>
          {/* The two lines a manager is actually steering between. */}
          <line className="chart-threshold is-healthy" x1={PAD.left} x2={w - PAD.right}
                y1={y(healthy)} y2={y(healthy)} />
          <text className="chart-threshold-label is-healthy" x={w - PAD.right} y={y(healthy) - 5}
                textAnchor="end">{healthy}% target</text>

          <line className="chart-threshold is-ceiling" x1={PAD.left} x2={w - PAD.right}
                y1={y(ceiling)} y2={y(ceiling)} />
          <text className="chart-threshold-label is-ceiling" x={w - PAD.right} y={y(ceiling) - 5}
                textAnchor="end">{ceiling}% ceiling</text>

          <text className="chart-tick" x={PAD.left - 8} y={y(0) + 3} textAnchor="end">0%</text>

          {days.map((d, i) => {
            if (d.percent == null) return null;
            const over = d.percent > ceiling;
            const tight = !over && d.percent > healthy;
            const top = y(d.percent);
            return (
              <rect
                key={i}
                className={`chart-bar${over ? " is-over" : tight ? " is-tight" : ""}`}
                x={PAD.left + i * band + 2}
                y={top}
                width={Math.max(2, band - 4)}
                height={Math.max(2, y(0) - top)}
                rx="3"
                onMouseEnter={() => setHover(i)}
              />
            );
          })}

          {days.map((d, i) => (
            <text key={`l${i}`} className="chart-tick"
                  x={PAD.left + i * band + band / 2} y={h - 6} textAnchor="middle">
              {shortDate(d.date)}
            </text>
          ))}
        </svg>

        {point && point.percent != null && (
          <div className="chart-tip"
               style={{ left: `${((PAD.left + hover * band + band / 2) / w) * 100}%` }}
               role="status">
            <strong>{point.date}</strong>
            <span>{point.percent}% of forecast</span>
          </div>
        )}
      </div>
    </Frame>
  );
}

/* ==========================================================================
   3. Magnitude, worst first — food cost, or anything else ranked
   ========================================================================== */

export function RankedBars({ title, note, items, unit = "%", limit, limitLabel }) {
  const [hover, setHover] = useHover();
  if (!items?.length) return null;

  const peak = Math.max(1, limit ?? 0, ...items.map((i) => i.value));

  return (
    <Frame
      title={title}
      note={note}
      table={{
        columns: ["Item", title],
        rows: items.map((i) => [i.label, `${i.value}${unit}`]),
      }}
    >
      <ul className="chart-bars">
        {items.map((item, i) => {
          const over = limit != null && item.value > limit;
          return (
            <li key={i}
                className={`chart-bars-row${over ? " is-over" : ""}${hover === i ? " is-hover" : ""}`}
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}>
              <span className="chart-bars-label">{item.label}</span>
              <span className="chart-bars-track">
                <span className="chart-bars-fill" style={{ width: `${(item.value / peak) * 100}%` }} />
                {limit != null && (
                  <span className="chart-bars-limit" style={{ left: `${(limit / peak) * 100}%` }}
                        aria-hidden="true" />
                )}
              </span>
              {/* Direct-labelled, so nothing here depends on reading a colour. */}
              <span className="chart-bars-value">{item.value}{unit}</span>
            </li>
          );
        })}
      </ul>
      {limit != null && limitLabel && (
        <p className="chart-foot"><span className="chart-foot-mark" aria-hidden="true" /> {limitLabel}</p>
      )}
    </Frame>
  );
}
