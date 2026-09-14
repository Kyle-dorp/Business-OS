/**
 * Empty, loading and error states.
 *
 * These three account for most of the roughness in an otherwise finished app,
 * because they are what a user sees on their first day, on a slow connection,
 * and when something breaks — and they are the screens nobody designs.
 *
 * The rules they follow:
 *
 *   Empty says what is missing and offers the action that fixes it. "No data"
 *   makes a reader wonder whether the page is broken.
 *
 *   Loading shows the shape of what is coming rather than a spinner, so the
 *   layout does not jump when it arrives.
 *
 *   Error says what failed and what to do. A stack trace is for us; a person
 *   mid-shift needs a sentence and a retry button.
 */

export function Empty({ title, children, action, actionLabel, icon = "○" }) {
  return (
    <div className="state-block">
      <span className="state-icon is-empty" aria-hidden="true">{icon}</span>
      <h3>{title}</h3>
      {children && <p>{children}</p>}
      {action && (
        <button className="primary-btn" onClick={action}>{actionLabel || "Get started"}</button>
      )}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "That didn't load" }) {
  // Backend messages are written for people and are worth showing. A raw
  // network failure is not, so it gets replaced with something actionable.
  const message =
    typeof error === "string" ? error : error?.message || "Something went wrong.";
  const isNetwork = /failed to fetch|networkerror|load failed/i.test(message);

  return (
    <div className="state-block">
      <span className="state-icon is-error" aria-hidden="true">!</span>
      <h3>{title}</h3>
      <p>
        {isNetwork
          ? "We couldn't reach the server. Check your connection and try again."
          : message}
      </p>
      {onRetry && <button className="ghost-btn" onClick={onRetry}>Try again</button>}
    </div>
  );
}

/**
 * Skeleton rows shaped roughly like the content they stand in for.
 * `lines` for text blocks, `rows` for table-ish content.
 */
export function Loading({ lines = 3, rows = 0, label = "Loading" }) {
  if (rows > 0) {
    return (
      <div role="status" aria-label={label}>
        {Array.from({ length: rows }, (_, i) => (
          <span key={i} className="skeleton tall" />
        ))}
      </div>
    );
  }
  const widths = ["w-80", "w-60", "w-40"];
  return (
    <div role="status" aria-label={label}>
      {Array.from({ length: lines }, (_, i) => (
        <span key={i} className={`skeleton ${widths[i % widths.length]}`} />
      ))}
    </div>
  );
}

/**
 * The three states in one call, for the common
 * "loading, then either error or data" shape.
 */
export function AsyncBoundary({ loading, error, onRetry, empty, emptyState, children }) {
  if (loading) return <Loading />;
  if (error) return <ErrorState error={error} onRetry={onRetry} />;
  if (empty) return emptyState || <Empty title="Nothing here yet" />;
  return children;
}
