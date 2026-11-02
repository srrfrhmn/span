import { addDays, differenceInCalendarDays, format } from "date-fns";
import { Settings2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { parse } from "../lib/dates";
import { useApp } from "../state/store";

interface Layout {
  cell: number;
  gap: number;
  rowH: number;
  left: number;
  top: number;
}

interface Tip {
  x: number;
  y: number;
  title: string;
  body: string;
}

export function LifeView() {
  const settings = useApp((state) => state.settings);
  const setView = useApp((state) => state.setView);
  const dataVersion = useApp((state) => state.dataVersion);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const layoutRef = useRef<Layout>({ cell: 8, gap: 2, rowH: 10, left: 34, top: 8 });
  const [tip, setTip] = useState<Tip | null>(null);

  const birth = parse(settings.birthDate);
  const lifespan = Math.max(1, settings.lifespan);
  const totalWeeks = lifespan * 52;
  const ageDays = Math.max(0, differenceInCalendarDays(new Date(), birth));
  const lived = Math.min(totalWeeks, Math.floor(ageDays / 7));
  const left = Math.max(0, totalWeeks - lived);
  const percent = Math.round((lived / totalWeeks) * 100);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const width = Math.max(320, wrap.clientWidth - 2);
    const leftPad = 36;
    const rightPad = 6;
    const topPad = 10;
    const gap = 2;
    const cell = Math.max(3, Math.min(13, Math.floor((width - leftPad - rightPad - 51 * gap) / 52)));
    const rowH = cell + gap;
    const height = topPad + lifespan * rowH + 6;
    const layout: Layout = { cell, gap, rowH, left: leftPad, top: topPad };
    layoutRef.current = layout;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const styles = getComputedStyle(document.documentElement);
    const livedColor = styles.getPropertyValue("--heat-5").trim() || "#5ee28d";
    const pastColor = styles.getPropertyValue("--heat-4").trim() || "#35a95d";
    const emptyColor = styles.getPropertyValue("--heat-0").trim() || "#222b26";
    const accent = styles.getPropertyValue("--accent").trim() || "#5ee28d";
    const muted = styles.getPropertyValue("--muted").trim() || "#8fa198";
    const font = styles.getPropertyValue("--font-ui").trim() || "system-ui";

    ctx.font = `10px ${font}`;
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    ctx.fillStyle = muted;

    const radius = Math.min(1.5, cell / 4);
    for (let year = 0; year < lifespan; year += 1) {
      if (year % 5 === 0) {
        ctx.fillText(String(year), leftPad - 8, topPad + year * rowH + cell / 2);
      }
      for (let week = 0; week < 52; week += 1) {
        const index = year * 52 + week;
        if (index >= totalWeeks) break;
        const x = leftPad + week * (cell + gap);
        const y = topPad + year * rowH;
        if (index < lived - 1) {
          ctx.fillStyle = pastColor;
        } else if (index < lived) {
          ctx.fillStyle = livedColor;
        } else {
          ctx.fillStyle = emptyColor;
        }
        ctx.beginPath();
        ctx.roundRect(x, y, cell, cell, radius);
        ctx.fill();
      }
    }

    // A subtle ring around the current week.
    if (lived < totalWeeks) {
      const row = Math.floor(lived / 52);
      const col = lived % 52;
      const x = leftPad + col * (cell + gap);
      const y = topPad + row * rowH;
      ctx.strokeStyle = accent;
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.roundRect(x - 1, y - 1, cell + 2, cell + 2, radius + 1);
      ctx.stroke();
    }
  }, [lifespan, totalWeeks, lived]);

  useEffect(() => {
    draw();
  }, [draw, settings.theme, settings.birthDate, dataVersion]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const observer = new ResizeObserver(() => draw());
    observer.observe(wrap);
    return () => observer.disconnect();
  }, [draw]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const id = window.requestAnimationFrame(() => {
      const row = Math.floor(lived / 52);
      const { rowH, top } = layoutRef.current;
      wrap.scrollTop = Math.max(0, top + row * rowH - wrap.clientHeight / 2);
    });
    return () => window.cancelAnimationFrame(id);
  }, [lived, settings.birthDate, settings.lifespan]);

  const onMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const { cell, gap, rowH, left: leftPad, top } = layoutRef.current;
    const x = event.clientX - rect.left - leftPad;
    const y = event.clientY - rect.top - top;
    const col = Math.floor(x / (cell + gap));
    const row = Math.floor(y / rowH);
    if (col < 0 || col > 51 || row < 0 || row >= lifespan) {
      setTip(null);
      return;
    }
    const index = row * 52 + col;
    if (index >= totalWeeks) {
      setTip(null);
      return;
    }
    const start = addDays(birth, index * 7);
    setTip({
      x: leftPad + col * (cell + gap) + cell / 2,
      y: top + row * rowH,
      title: `Age ${row} · Week ${col + 1}`,
      body: format(start, "MMM d, yyyy"),
    });
  };

  const years = Math.floor(ageDays / 365.25);

  return (
    <div className="page life-page">
      <header className="page-head">
        <div className="page-head__titles">
          <span className="eyebrow">Life</span>
          <h1>Your span</h1>
          <p className="page-head__sub">
            {years} years old · {percent}% of an expected {lifespan}-year life
          </p>
        </div>
        <div className="page-head__actions">
          <button className="btn ghost small" onClick={() => setView("settings")}>
            <Settings2 size={14} /> Adjust
          </button>
        </div>
      </header>

      <div className="life-stats">
        <div>
          <strong>{lived.toLocaleString()}</strong>
          <span>weeks lived</span>
        </div>
        <div>
          <strong>{left.toLocaleString()}</strong>
          <span>weeks ahead</span>
        </div>
        <div>
          <strong>{percent}%</strong>
          <span>of your span</span>
        </div>
        <div className="life-stats__legend">
          <span>
            <i className="legend__cell heat-5" /> lived
          </span>
          <span>
            <i className="legend__cell heat-0" /> ahead
          </span>
        </div>
      </div>

      <section className="panel life-panel">
        <div className="life-scroll" ref={wrapRef}>
          <div className="life-canvas-wrap">
            <canvas
              ref={canvasRef}
              onMouseMove={onMove}
              onMouseLeave={() => setTip(null)}
            />
            {tip ? (
              <div className="life-tip" style={{ left: tip.x, top: tip.y }}>
                <strong>{tip.title}</strong>
                <span>{tip.body}</span>
              </div>
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
