/**
 * A surface.
 *
 * The version this replaces set `el.style.transform`, `el.style.boxShadow` and
 * `el.style.borderColor` from onMouseEnter and onMouseLeave handlers, reaching
 * for var(--shadow-sm), var(--shadow-lg) and var(--shadow-glow) — none of
 * which this product defines. A var() naming nothing does not fall back; it
 * invalidates the declaration, so the card would have had no shadow at all
 * rather than a wrong one, and that reads as a design choice.
 *
 * Hover belongs in CSS. It survives the element re-rendering, it respects
 * prefers-reduced-motion, and it can be read by the checks.
 */

import { forwardRef } from "react";

const Card = forwardRef(function Card(
  { as: Tag = "div", interactive, onClick, className = "", children, ...rest },
  ref,
) {
  // Interactive means "this does something when you press it". It defaults to
  // whether there is anything to press, because a surface that lifts under the
  // cursor and then does nothing is a lie about what it is.
  const lifts = interactive ?? Boolean(onClick);
  const isButton = lifts && Tag === "div";

  return (
    <Tag
      ref={ref}
      className={`eos-card${lifts ? " eos-card-interactive" : ""} ${className}`.trim()}
      onClick={onClick}
      // A div that responds to a click has to be reachable and pressable
      // without a mouse, or it is furniture for anyone using a keyboard.
      role={isButton ? "button" : undefined}
      tabIndex={isButton ? 0 : undefined}
      onKeyDown={
        isButton
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onClick?.(event);
              }
            }
          : undefined
      }
      {...rest}
    >
      {children}
    </Tag>
  );
});

export { Card };
export default Card;
