import React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'tertiary';
  size?: 'sm' | 'md' | 'lg';
  /** Rendered before the label. Any node — an icon component, an emoji, an SVG. */
  icon?: React.ReactNode;
  /** Swaps the icon for a spinner and blocks interaction while work is in flight. */
  loading?: boolean;
  children: React.ReactNode;
}

const PADDING = { sm: '8px 16px', md: '12px 24px', lg: '14px 32px' } as const;
const FONT_SIZE = { sm: '14px', md: '15px', lg: '16px' } as const;

const Spinner: React.FC = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    style={{ animation: 'eos-spin 0.7s linear infinite', flex: 'none' }}
  >
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeOpacity="0.25" strokeWidth="3" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
  </svg>
);

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      icon,
      loading = false,
      disabled,
      className = '',
      children,
      style,
      ...props
    },
    ref
  ) => {
    // A button mid-request must not be clickable again, whatever the caller passed.
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        className={`btn btn-${variant} btn-${size} ${className}`}
        style={{
          background: 'transparent',
          color: variant === 'primary' ? 'var(--accent)' : 'var(--text-muted)',
          padding: PADDING[size],
          fontSize: FONT_SIZE[size],
          border: variant === 'secondary' ? '1px solid #e5e7eb' : 'none',
          borderRadius: '6px',
          fontWeight: variant === 'primary' ? 600 : 500,
          cursor: isDisabled ? 'not-allowed' : 'pointer',
          opacity: isDisabled ? 0.6 : 1,
          transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          ...style,
        }}
        {...props}
      >
        {loading ? <Spinner /> : icon ? <span style={{ display: 'inline-flex', flex: 'none' }}>{icon}</span> : null}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

// Exported both ways on purpose: the page components import it as a named
// export, App.tsx imports it as default. Supporting both is one line and
// removes a whole class of build failure.
export { Button };
export default Button;
