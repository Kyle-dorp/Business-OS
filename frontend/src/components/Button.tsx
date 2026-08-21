import React from 'react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading = false, icon, children, className = '', ...props }, ref) => {
    const baseClasses = 'font-medium rounded-lg transition-all duration-300 inline-flex items-center justify-center gap-2'
    
    const variantClasses = {
      primary: 'bg-blue-500 text-white hover:bg-blue-600 shadow-card hover:shadow-hover hover:-translate-y-0.5',
      secondary: 'bg-white border border-gray-300 text-gray-900 hover:bg-gray-50',
      ghost: 'text-gray-900 hover:bg-gray-100',
      danger: 'bg-red-500 text-white hover:bg-red-600',
    }
    
    const sizeClasses = {
      sm: 'px-4 py-2 text-sm',
      md: 'px-6 py-3',
      lg: 'px-8 py-4 text-lg',
    }
    
    return (
      <button
        ref={ref}
        className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
        disabled={loading || props.disabled}
        {...props}
      >
        {loading && <span className="animate-spin">⚡</span>}
        {icon && !loading && icon}
        {children}
      </button>
    )
  }
)

Button.displayName = 'Button'
