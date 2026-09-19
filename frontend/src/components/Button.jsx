/**
 * The only button.
 *
 * The version this replaces styled itself from a JavaScript style object:
 * `1px solid #e5e7eb` for its border, `cubic-bezier(0.4, 0, 0.2, 1)` for its
 * transition — a second easing curve competing with the theme's — and
 * `var(--text-muted)` for its text, which is not a token this product defines.
 * It was imported by none of the twenty pages, which is the only reason none
 * of that was visible.
 *
 * This one carries no styling at all. Everything is in theme-primitives.css,
 * where the design-system checks can read it.
 */

import { forwardRef } from "react";

function Spinner() {
  return (
    <svg className="eos-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

const Button = forwardRef(function Button(
  { variant = "primary", size = "md", icon, loading = false, disabled, className = "", children, ...rest },
  ref,
) {
  // A button mid-request must not be clickable again, whatever the caller
  // passed. Double-submitting a payment is not the caller's mistake to make.
  const blocked = disabled || loading;

  return (
    <button
      ref={ref}
      disabled={blocked}
      aria-busy={loading || undefined}
      className={`eos-btn eos-btn-${variant} eos-btn-${size} ${className}`.trim()}
      {...rest}
    >
      {loading ? <Spinner /> : icon ? <span className="eos-btn-icon" aria-hidden="true">{icon}</span> : null}
      {children}
    </button>
  );
});

export { Button };
export default Button;
