import { useEffect, useRef, useState } from "react";

/**
 * Animate a number toward its new value.
 *
 * A price that jumps from $39 to $49 is a number. A price that travels there is
 * a product telling you it heard the click — and on the billing page that click
 * is somebody deciding what to spend, which is the one moment worth making feel
 * deliberate.
 *
 * Eased out rather than linear: fast at the start so it feels responsive, slow
 * at the end so the final figure settles rather than snaps.
 *
 * Honours prefers-reduced-motion by skipping straight to the value. Motion is
 * decoration here; the number is the content, and somebody who has asked for
 * less movement still gets the number.
 */
export function useCountUp(target, { duration = 520 } = {}) {
  const [display, setDisplay] = useState(target);
  const fromRef = useRef(target);
  const frameRef = useRef(0);

  useEffect(() => {
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const from = fromRef.current;
    const to = Number(target) || 0;

    if (reduced || from === to) {
      fromRef.current = to;
      setDisplay(to);
      return undefined;
    }

    const started = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - started) / duration, 1);
      // easeOutCubic
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = from + (to - from) * eased;
      setDisplay(value);
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };

    frameRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameRef.current);
  }, [target, duration]);

  return display;
}
