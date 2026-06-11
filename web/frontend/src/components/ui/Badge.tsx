import React from 'react'

interface BadgeProps {
  variant?: 'primary' | 'success' | 'warning' | 'error' | 'neutral'
  size?: 'sm' | 'md'
  children: React.ReactNode
  className?: string
}

export const Badge = ({
  variant = 'primary',
  size = 'sm',
  children,
  className = '',
}: BadgeProps) => {
  const variantClass = {
    primary: 'bg-primary-100 text-primary-800 dark:bg-primary-900 dark:text-primary-200',
    success: 'bg-accent-100 text-accent-800 dark:bg-accent-900 dark:text-accent-200',
    warning: 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200',
    error: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    neutral: 'bg-neutral-100 text-neutral-800 dark:bg-neutral-900 dark:text-neutral-200',
  }

  const sizeClass = {
    sm: 'px-2.5 py-1 text-xs font-medium rounded',
    md: 'px-3 py-1.5 text-sm font-medium rounded-md',
  }

  return (
    <span className={`inline-block ${variantClass[variant]} ${sizeClass[size]} ${className}`}>
      {children}
    </span>
  )
}
