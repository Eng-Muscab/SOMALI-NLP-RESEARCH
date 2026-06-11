import React, { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { Menu, X, BarChart3, Brain, Upload, Zap, LogOut, Moon, Sun } from 'lucide-react'
import { useTheme } from '@contexts/ThemeContext'
import { useAuth } from '@hooks/useAuth'
import { Button } from './ui/Button'

export const Layout = () => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const { theme, toggleTheme } = useTheme()
  const { user, logout } = useAuth()

  const navItems = [
    { path: '/', icon: <BarChart3 size={20} />, label: 'Dashboard' },
    { path: '/predict', icon: <Brain size={20} />, label: 'Predict' },
    { path: '/models', icon: <Zap size={20} />, label: 'Models' },
    { path: '/experiments', icon: <BarChart3 size={20} />, label: 'Experiments' },
    { path: '/datasets', icon: <Upload size={20} />, label: 'Datasets' },
  ]

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="flex h-screen bg-neutral-50 dark:bg-neutral-900">
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`
          fixed lg:relative z-50 h-full w-64 bg-white dark:bg-neutral-800 border-r border-neutral-200 dark:border-neutral-700
          transition-transform duration-300 transform
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          lg:block
        `}
      >
        <div className="flex flex-col h-full">
          <div className="px-6 py-6 border-b border-neutral-200 dark:border-neutral-700">
            <div className="flex items-center justify-between">
              <Link to="/" className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-600 to-accent-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold">S</span>
                </div>
                <span className="font-bold text-lg text-neutral-900 dark:text-white">SNLP</span>
              </Link>
              <button
                onClick={() => setMobileOpen(false)}
                className="lg:hidden text-neutral-500"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                className={`
                  flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200
                  ${isActive(item.path)
                    ? 'bg-primary-100 dark:bg-primary-900 text-primary-700 dark:text-primary-200'
                    : 'text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700'
                  }
                `}
              >
                {item.icon}
                <span className="font-medium">{item.label}</span>
              </Link>
            ))}
          </nav>

          <div className="px-4 py-6 border-t border-neutral-200 dark:border-neutral-700 space-y-2">
            <button
              onClick={toggleTheme}
              className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-all duration-200"
            >
              {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
              <span className="font-medium">{theme === 'light' ? 'Dark' : 'Light'}</span>
            </button>
            <button
              onClick={logout}
              className="w-full flex items-center space-x-3 px-4 py-3 rounded-lg text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-all duration-200"
            >
              <LogOut size={20} />
              <span className="font-medium">Sign out</span>
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white dark:bg-neutral-800 border-b border-neutral-200 dark:border-neutral-700 flex items-center px-6 space-x-4">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden text-neutral-600 dark:text-neutral-400"
          >
            <Menu size={24} />
          </button>

          <div className="flex-1"></div>

          <div className="flex items-center space-x-4">
            <div className="hidden sm:flex items-center space-x-2 px-3 py-2 bg-neutral-100 dark:bg-neutral-700 rounded-lg">
              <span className="text-sm font-medium text-neutral-700 dark:text-neutral-200">
                {user?.name ?? user?.email ?? 'Researcher'}
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={logout}>
              Logout
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
