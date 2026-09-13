import React from 'react';

export interface CardProps {
  children: React.ReactNode;
  /** Lift and glow on pointer-over. */
  hover?: boolean;
  /** Alias for `hover`. Both spellings exist across the pages; both work. */
  hoverable?: boolean;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ children, hover, hoverable, onClick, className = '', style = {} }, ref) => {
    // Either prop turns it on; default is on when neither is given.
    const lifts = hover ?? hoverable ?? true;
    const clickable = Boolean(onClick);

    const settle = (el: HTMLElement) => {
      el.style.transform = 'translateY(0)';
      el.style.boxShadow = 'var(--shadow-sm)';
      el.style.borderColor = '#f0f0f0';
    };

    const raise = (el: HTMLElement) => {
      el.style.transform = 'translateY(-2px)';
      el.style.boxShadow = 'var(--shadow-lg), var(--shadow-glow)';
      el.style.borderColor = 'var(--accent)';
    };

    return (
      <div
        ref={ref}
        onClick={onClick}
        // A clickable div is invisible to keyboards and screen readers unless
        // it is told it behaves like a button.
        role={clickable ? 'button' : undefined}
        tabIndex={clickable ? 0 : undefined}
        onKeyDown={
          clickable
            ? (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onClick?.();
                }
              }
            : undefined
        }
        className={`card ${className}`}
        style={{
          background: 'var(--surface)',
          border: '1px solid #f0f0f0',
          borderRadius: '8px',
          padding: '24px',
          boxShadow: 'var(--shadow-sm)',
          cursor: clickable ? 'pointer' : 'default',
          transition: 'all 0.3s ease',
          ...style,
        }}
        onMouseEnter={(e) => lifts && raise(e.currentTarget)}
        onMouseLeave={(e) => lifts && settle(e.currentTarget)}
        onFocus={(e) => lifts && clickable && raise(e.currentTarget)}
        onBlur={(e) => lifts && clickable && settle(e.currentTarget)}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

// Named and default, for the same reason as Button.
export { Card };
export default Card;
