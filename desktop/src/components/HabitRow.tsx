import { Check, Flame } from "lucide-react";
import type { Habit } from "../lib/ipc";

interface HabitRowProps {
  habit: Habit;
  done: boolean;
  streak: number;
  week: { day: string; done: boolean; label: string }[];
  onToggle: () => void;
}

export function HabitRow({ habit, done, streak, week, onToggle }: HabitRowProps) {
  return (
    <button
      type="button"
      className={`habit-row ${done ? "is-done" : ""}`}
      onClick={onToggle}
      aria-pressed={done}
      aria-label={`${habit.name}, ${done ? "completed" : "not completed"}`}
    >
      <span className="habit-row__check" aria-hidden>
        <Check size={15} strokeWidth={2.6} />
      </span>

      <span className="habit-row__body">
        <span className="habit-row__name">{habit.name}</span>
        <span className="habit-row__meta">
          <span className="habit-row__dots" aria-hidden>
            {week.map((day) => (
              <span
                key={day.day}
                className={`habit-dot ${day.done ? "is-done" : ""}`}
                title={day.label}
              />
            ))}
          </span>
          <span className="habit-row__streak">
            <Flame size={12} />
            {streak > 0 ? `${streak}d` : "—"}
          </span>
        </span>
      </span>
    </button>
  );
}
