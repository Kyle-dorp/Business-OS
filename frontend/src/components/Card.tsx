import React from 'react'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean
  header?: React.ReactNode
  footer?: React.ReactNode
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ hoverable = false, header, footer, children, className = '', ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`card ${hoverable ? 'card-hover' : ''} ${className}`}
        {...props}
      >
        {header && <div className="mb-4 pb-4 border-b border-gray-200">{header}</div>}
        {children}
        {footer && <div className="mt-4 pt-4 border-t border-gray-200">{footer}</div>}
      </div>
    )
  }
)

Card.displayName = 'Card'
