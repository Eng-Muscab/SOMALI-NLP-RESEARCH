import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { Menu, X, BarChart3, Brain, Zap, LogOut, User as UserIcon } from 'lucide-react'
import { motion } from 'framer-motion'
import { useAuth } from '@hooks/useAuth'
import { Button } from './ui/Button'

export const Layout = () => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()
  const { user, logout } = useAuth()

  const navItems = [
    { path: '/', icon: <BarChart3 size={18} />, label: 'Dashboard' },
    { path: '/predict', icon: <Brain size={18} />, label: 'Predict' },
    { path: '/models', icon: <Zap size={18} />, label: 'Models' },
    { path: '/experiments', icon: <BarChart3 size={18} />, label: 'Experiments' },
  ]

  const isActive = (path: string) => location.pathname === path

  return (
    <div className="flex h-screen bg-neutral-50 dark:bg-neutral-950 transition-colors duration-300">
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={`
          fixed lg:relative z-50 h-full w-64 bg-white dark:bg-neutral-900 border-r border-neutral-200/60 dark:border-neutral-800/80
          transition-transform duration-300 transform
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          lg:block
        `}
      >
        <div className="flex flex-col h-full">
          <div className="px-6 py-6 border-b border-neutral-100 dark:border-neutral-800/60">
            <div className="flex items-center justify-between">
              <Link to="/" className="flex items-center space-x-3">
                <div className="w-9 h-9 bg-gradient-to-tr from-primary-600 to-accent-500 rounded-xl flex items-center justify-center shadow-lg shadow-primary-500/20">
                  <span className="text-white font-black text-lg">S</span>
                </div>
                <span className="font-extrabold text-xl tracking-tight bg-gradient-to-r from-neutral-900 to-neutral-700 dark:from-white dark:to-neutral-300 bg-clip-text text-transparent">SNLP Research</span>
              </Link>
              <button
                onClick={() => setMobileOpen(false)}
                className="lg:hidden text-neutral-500 hover:text-neutral-700 dark:hover:text-neutral-300"
              >
                <X size={20} />
              </button>
            </div>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-1.5 overflow-y-auto">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                onClick={() => setMobileOpen(false)}
                className={`
                  flex items-center space-x-3 px-4 py-3 rounded-xl transition-all duration-300 relative group
                  ${isActive(item.path)
                    ? 'text-primary-600 dark:text-primary-400 font-bold bg-primary-50/50 dark:bg-primary-500/5'
                    : 'text-neutral-500 dark:text-neutral-400 hover:bg-neutral-50 dark:hover:bg-neutral-800/40 hover:text-neutral-900 dark:hover:text-neutral-100'
                  }
                `}
              >
                {isActive(item.path) && (
                  <motion.div
                    layoutId="activeNavIndicator"
                    className="absolute left-0 top-1/4 bottom-1/4 w-1 bg-gradient-to-b from-primary-600 to-accent-500 rounded-r-full"
                    transition={{ type: "spring", stiffness: 380, damping: 30 }}
                  />
                )}
                <span className={`transition-transform duration-300 group-hover:scale-110 ${isActive(item.path) ? 'text-primary-500' : 'text-neutral-400'}`}>
                  {item.icon}
                </span>
                <span className="text-sm tracking-wide">{item.label}</span>
              </Link>
            ))}
          </nav>

          <div className="px-4 py-6 border-t border-neutral-100 dark:border-neutral-800/60 space-y-1.5">
            <button
              onClick={logout}
              className="w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-rose-600 dark:text-rose-400 hover:bg-rose-50/70 dark:hover:bg-rose-950/20 transition-all duration-300 group"
            >
              <span className="text-red-500 transition-transform duration-300 group-hover:translate-x-0.5">
                <LogOut size={18} />
              </span>
              <span className="text-sm font-semibold tracking-wide text-red-600 dark:text-red-400">Sign out</span>
            </button>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 bg-white/80 dark:bg-neutral-900/80 backdrop-blur-md border-b border-neutral-200/50 dark:border-neutral-800/50 flex items-center px-6 justify-between shrink-0 z-30">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden text-neutral-600 dark:text-neutral-400 p-1 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-lg"
          >
            <Menu size={22} />
          </button>

          <div className="flex-1"></div>

          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-2.5 px-3 py-1.5 bg-neutral-100/70 dark:bg-neutral-800/50 border border-neutral-200/10 dark:border-neutral-700/20 rounded-xl">
              <div className="w-6 h-6 rounded-lg bg-primary-100 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400 flex items-center justify-center">
                <UserIcon size={13} />
              </div>
              <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 max-w-[140px] truncate">
                {user?.name ?? user?.email ?? 'Researcher'}
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={logout} className="text-xs py-1.5 px-3">
              Logout
            </Button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="p-6 lg:p-8 max-w-7xl mx-auto w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
