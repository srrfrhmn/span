import { Check } from "lucide-react";
import type { ThemeKey } from "../lib/ipc";
import { THEMES } from "../lib/themes";

interface ThemePickerProps {
  value: ThemeKey;
  onChange: (key: ThemeKey) => void;
}

export function ThemePicker({ value, onChange }: ThemePickerProps) {
  return (
    <div className="theme-grid" role="radiogroup" aria-label="Color theme">
      {THEMES.map((theme) => {
        const selected = theme.key === value;
        return (
          <button
            key={theme.key}
            type="button"
            role="radio"
            aria-checked={selected}
            className={`theme-chip ${selected ? "is-selected" : ""}`}
            onClick={() => onChange(theme.key)}
          >
            <span className="theme-chip__swatches" aria-hidden>
              {theme.swatches.map((color) => (
                <span key={color} style={{ background: color }} />
              ))}
            </span>
            <span className="theme-chip__label">
              {theme.label}
              {selected ? <Check size={13} /> : null}
            </span>
          </button>
        );
      })}
    </div>
  );
}
