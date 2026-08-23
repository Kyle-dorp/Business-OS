import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'tertiary';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', className = '', ...props }, ref) => {
    const variantClass = `btn-${variant}`;
    const sizeClass = `btn-${size}`;

    return (
      <button
        ref={ref}
        className={`btn ${variantClass} ${sizeClass} ${className}`}
        style={{
          background: 'transparent',
          color: variant === 'primary' ? 'var(--accent)' : 'var(--text-muted)',
          padding: size === 'sm' ? '8px 16px' : size === 'lg' ? '14px 32px' : '12px 24px',
          fontSize: size === 'sm' ? '14px' : size === 'lg' ? '16px' : '15px',
          border: variant === 'secondary' ? '1px solid #e5e7eb' : 'none',
          borderRadius: '6px',
          fontWeight: variant === 'primary' ? 600 : 500,
          cursor: 'pointer',
          transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
        }}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';

export default Button;
