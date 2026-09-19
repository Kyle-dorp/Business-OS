/**
 * Which theme is on, and which accent.
 *
 * Two independent axes, both written to <html> as data attributes, because
 * that is where theme.css reads them: [data-theme] picks the ground, and
 * [data-accent] picks the ramp the ground draws its interaction colour from.
 * Keeping them separate is what stops three themes times four accents being
 * twelve stylesheets.
 *
 * The first visit has no stored answer, so it follows the operating system.
 * Choosing explicitly stores it, and from then on the choice wins — someone
 * who picked light does not want their laptop switching them to dark at
 * sunset.
 *
 * localStorage can throw outright in a private window or with site data
 * blocked, which is a strange way to lose an entire app, so every read and
 * write is wrapped.
 */

import { useCallback, useEffect, useState } from "react";

export const THEMES = ["light", "dark", "neutral"];
export const ACCENTS = ["amber", "indigo", "azure", "violet"];

const THEME_KEY = "eos.theme";
const ACCENT_KEY = "eos.accent";

function stored(key, allowed) {
  try {
    const value = window.localStorage.getItem(key);
    return allowed.includes(value) ? value : null;
  } catch {
    return null;
  }
}

function remember(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* Storage is a convenience here. The app works without it. */
  }
}

function systemPreference() {
  try {
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  } catch {
    return "dark";
  }
}

export function useTheme() {
  const [theme, setThemeState] = useState(() => stored(THEME_KEY, THEMES) || systemPreference());
  const [accent, setAccentState] = useState(() => stored(ACCENT_KEY, ACCENTS) || "amber");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.setAttribute("data-accent", accent);
  }, [accent]);

  // Only while the choice is still the system's. Once somebody picks, their
  // pick stands.
  useEffect(() => {
    if (stored(THEME_KEY, THEMES)) return undefined;
    let media;
    try {
      media = window.matchMedia("(prefers-color-scheme: light)");
    } catch {
      return undefined;
    }
    const follow = (event) => setThemeState(event.matches ? "light" : "dark");
    media.addEventListener?.("change", follow);
    return () => media.removeEventListener?.("change", follow);
  }, []);

  const setTheme = useCallback((next) => {
    if (!THEMES.includes(next)) return;
    remember(THEME_KEY, next);
    setThemeState(next);
  }, []);

  const setAccent = useCallback((next) => {
    if (!ACCENTS.includes(next)) return;
    remember(ACCENT_KEY, next);
    setAccentState(next);
  }, []);

  return { theme, setTheme, accent, setAccent };
}
