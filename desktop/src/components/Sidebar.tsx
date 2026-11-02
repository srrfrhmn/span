import {
  CalendarDays,
  Command,
  Flame,
  Grid3x3,
  Hourglass,
  Settings,
  Sun,
} from "lucide-react";
import { useApp, type View } from "../state/store";

const NAV: { id: View; label: string; icon: typeof Sun }[] = [
  { id: "today", label: "Today", icon: Sun },
  { id: "month", label: "Month", icon: CalendarDays },
  { id: "year", label: "Year", icon: Grid3x3 },
  { id: "life", label: "Life", icon: Hourglass },
];

export function Sidebar() {
  const view = useApp((state) => state.view);
  const streak = useApp((state) => state.streak);
  const setView = useApp((state) => state.setView);
  const setPalette = useApp((state) => state.setPalette);

  return (
    <aside className="sidebar">
      <nav className="nav" aria-label="Views">
        <p className="nav__eyebrow">Views</p>
        {NAV.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`nav__item ${view === id ? "is-active" : ""}`}
            onClick={() => setView(id)}
            aria-current={view === id ? "page" : undefined}
          >
            <Icon size={17} strokeWidth={1.8} />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar__foot">
        <button className="streak-card" onClick={() => setView("today")}>
          <span className="streak-card__icon">
            <Flame size={16} />
          </span>
          <span>
            <span className="streak-card__label">Current streak</span>
            <span className="streak-card__value">
              {streak} {streak === 1 ? "day" : "days"}
            </span>
          </span>
        </button>

        <button className="nav__item" onClick={() => setView("settings")} aria-current={view === "settings" ? "page" : undefined}>
          <Settings size={17} strokeWidth={1.8} />
          <span>Preferences</span>
        </button>

        <button className="kbd-hint" onClick={() => setPalette(true)}>
          <Command size={12} />
          <span>K</span>
          <em>Quick actions</em>
        </button>
      </div>
    </aside>
  );
}
