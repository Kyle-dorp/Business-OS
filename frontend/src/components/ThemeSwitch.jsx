/**
 * Picking the ground and the light.
 *
 * Theme choice usually hides in a settings page, which is the one place
 * nobody looks while deciding whether a product feels right. It sits in the
 * topbar instead: the whole app repaints under the cursor, which is both the
 * fastest way to choose and the most convincing thing the interface does.
 *
 * The accent row is here so the accent can be chosen by looking rather than
 * by reading hex codes. Whether it stays is a product decision — a single
 * baked accent is a brand, four is a preference.
 */

import { useEffect, useRef, useState } from "react";
import { ACCENTS, THEMES } from "../hooks/useTheme";

const THEME_LABEL = {
  light: "Light",
  dark: "Dark",
  neutral: "Neutral",
};

const THEME_HINT = {
  light: "Daylight",
  dark: "A warm room at night",
  neutral: "Cool graphite",
};

const ACCENT_LABEL = {
  amber: "Amber",
  indigo: "Indigo",
  azure: "Azure",
  violet: "Violet",
};

export default function ThemeSwitch({ theme, setTheme, accent, setAccent }) {
  const [open, setOpen] = useState(false);
  const root = useRef(null);

  // Click-away and Escape. A popover you cannot dismiss is a modal nobody
  // asked for.
  useEffect(() => {
    if (!open) return undefined;
    const away = (event) => {
      if (root.current && !root.current.contains(event.target)) setOpen(false);
    };
    const escape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  return (
    <div className="theme-switch" ref={root}>
      <button
        className="theme-switch-trigger"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="true"
        aria-label={`Appearance: ${THEME_LABEL[theme]}. Change it`}
        title="Appearance"
      >
        <span className="theme-switch-orb" aria-hidden="true" />
      </button>

      {open && (
        <div className="theme-panel" role="dialog" aria-label="Appearance">
          <p className="theme-panel-title">Appearance</p>
          <div className="theme-row">
            {THEMES.map((option) => (
              <button
                key={option}
                className={`theme-chip${theme === option ? " is-on" : ""}`}
                onClick={() => setTheme(option)}
                aria-pressed={theme === option}
              >
                <span className={`theme-chip-swatch swatch-${option}`} aria-hidden="true" />
                <span className="theme-chip-label">{THEME_LABEL[option]}</span>
                <span className="theme-chip-hint">{THEME_HINT[option]}</span>
              </button>
            ))}
          </div>

          <p className="theme-panel-title">Accent</p>
          <div className="accent-row">
            {ACCENTS.map((option) => (
              <button
                key={option}
                className={`accent-dot${accent === option ? " is-on" : ""}`}
                data-accent={option}
                onClick={() => setAccent(option)}
                aria-pressed={accent === option}
                aria-label={ACCENT_LABEL[option]}
                title={ACCENT_LABEL[option]}
              >
                <span aria-hidden="true" />
              </button>
            ))}
          </div>
          <p className="theme-panel-foot">
            Money keeps its own colours — mint is kept, rose is leaving — in every
            combination.
          </p>
        </div>
      )}
    </div>
  );
}
