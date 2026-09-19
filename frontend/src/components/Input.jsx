/**
 * The only field.
 *
 * The version this replaces was styled entirely in Tailwind classes — w-full,
 * text-gray-700, ring-2 ring-red-500, input-base — and Tailwind was removed
 * from this project along with its config. Every one of those class names
 * matched nothing, so the component rendered as an unstyled browser input
 * inside an unstyled div. Nothing caught it because no page imported it.
 *
 * Label, hint and error are built in because a field with its error message
 * bolted on from outside is a field where somebody eventually forgets, and
 * because the hint and the error share one slot: showing either must not move
 * the rest of the form.
 */

import { forwardRef, useId } from "react";

const Input = forwardRef(function Input(
  { label, hint, error, required, className = "", id, as = "input", ...rest },
  ref,
) {
  const generated = useId();
  const fieldId = id || generated;
  const noteId = `${fieldId}-note`;
  const Tag = as;

  return (
    <div className="eos-field">
      {label && (
        <label className="eos-label" htmlFor={fieldId}>
          {label}
          {required && (
            <span className="eos-required" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}

      <Tag
        ref={ref}
        id={fieldId}
        required={required}
        // The message is announced with the field rather than read out as a
        // stray sentence somewhere after it.
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? noteId : undefined}
        className={`eos-input${error ? " eos-input-invalid" : ""} ${className}`.trim()}
        {...rest}
      />

      {/* One slot. An error replaces the hint rather than pushing it down. */}
      {error ? (
        <p className="eos-error" id={noteId} role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="eos-hint" id={noteId}>
          {hint}
        </p>
      ) : null}
    </div>
  );
});

export { Input };
export default Input;
