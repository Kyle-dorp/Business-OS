import React from 'react';

interface CardProps {
  children: React.ReactNode;
  hover?: boolean;
  onClick?: () => void;
  className?: string;
  style?: React.CSSProperties;
}

const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ children, hover = true, onClick, className = '', style = {} }, ref) => {
    return (
      <div
        ref={ref}
        onClick={onClick}
        className={`card ${className}`}
        style={{
          background: 'var(--surface)',
          border: '1px solid #f0f0f0',
          borderRadius: '8px',
          padding: '24px',
          boxShadow: 'var(--shadow-sm)',
          cursor: onClick ? 'pointer' : 'default',
          transition: 'all 0.3s ease',
          ...style,
        }}
        onMouseEnter={(e) => {
          if (hover) {
            (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)';
            (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-lg), var(--shadow-glow)';
            (e.currentTarget as HTMLElement).style.borderColor = 'var(--accent)';
          }
        }}
        onMouseLeave={(e) => {
          if (hover) {
            (e.currentTarget as HTMLElement).style.transform = 'translateY(0)';
            (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-sm)';
            (e.currentTarget as HTMLElement).style.borderColor = '#f0f0f0';
          }
        }}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';

export default Card;
