import React from 'react'

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  hover?: boolean
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ className = '', hover = false, children, ...props }, ref) => (
    <div
      ref={ref}
      className={`
        bg-white dark:bg-neutral-800 rounded-lg border border-neutral-200 dark:border-neutral-700
        shadow-xs transition-all duration-200
        ${hover ? 'hover:shadow-md hover:border-neutral-300 dark:hover:border-neutral-600 cursor-pointer' : ''}
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  )
)
Card.displayName = 'Card'

interface CardHeaderProps {
  children: React.ReactNode
  className?: string
}

export const CardHeader = ({ children, className = '' }: CardHeaderProps) => (
  <div className={`px-6 py-4 border-b border-neutral-200 dark:border-neutral-700 ${className}`}>
    {children}
  </div>
)

interface CardContentProps {
  children: React.ReactNode
  className?: string
}

export const CardContent = ({ children, className = '' }: CardContentProps) => (
  <div className={`px-6 py-4 ${className}`}>
    {children}
  </div>
)

interface CardFooterProps {
  children: React.ReactNode
  className?: string
}

export const CardFooter = ({ children, className = '' }: CardFooterProps) => (
  <div className={`px-6 py-4 border-t border-neutral-200 dark:border-neutral-700 ${className}`}>
    {children}
  </div>
)
