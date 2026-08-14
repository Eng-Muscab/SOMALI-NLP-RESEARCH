import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  Menu, X, BarChart3, Brain, Zap, LogOut,
  FlaskConical, LineChart, Users, ScrollText, ChevronDown, Shield,
  Sun, Moon, Microscope, Newspaper, Link2,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@hooks/useAuth'
import { isAdmin } from '@/types/auth'
import { useTheme } from '@/contexts/ThemeContext'

export const Layout = () => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [adminExpanded, setAdminExpanded] = useState(false)
  const location = useLocation()
  const { user, logout } = useAuth()
  const adminUser = isAdmin(user)
  const { theme, toggleTheme } = useTheme()

  const mainNav = [
    { path: '/dashboard',   icon: <BarChart3 size={15} />,    label: 'Dashboard'      },
    { path: '/predict',     icon: <Brain size={15} />,        label: 'Predict'        },
    { path: '/link',        icon: <Link2 size={15} />,        label: 'Analyse Link'   },
    { path: '/news',        icon: <Newspaper size={15} />,    label: 'News Feed'      },
    { path: '/models',      icon: <Zap size={15} />,          label: 'Models'         },
    { path: '/experiments', icon: <FlaskConical size={15} />, label: 'Experiments'    },
    { path: '/xai',         icon: <Microscope size={15} />,   label: 'Explainability' },
    { path: '/analytics',   icon: <LineChart size={15} />,    label: 'Analytics'      },
  ]
  const adminNav = [
    { path: '/admin/users', icon: <Users size={15} />,       label: 'Users'      },
    { path: '/admin/logs',  icon: <ScrollText size={15} />,  label: 'Audit Logs' },
  ]

  const isActive = (path: string) => location.pathname.startsWith(path)
  const isAdminSection = adminNav.some(item => location.pathname.startsWith(item.path))

  const NavItem = ({ path, icon, label }: { path: string; icon: React.ReactNode; label: string }) => {
    const active = isActive(path)
    return (
      <Link
        to={path}
        onClick={() => setMobileOpen(false)}
        className={`relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-semibold transition-colors duration-150 ${
          active
            ? 'bg-sky-500/10 text-sky-600 dark:bg-sky-400/10 dark:text-sky-300'
            : 'text-neutral-500 hover:bg-neutral-100/80 hover:text-neutral-800 dark:text-neutral-500 dark:hover:bg-white/5 dark:hover:text-neutral-200'
        }`}
      >
        {active && (
          <motion.div
            layoutId="nav-pill"
            className="absolute inset-0 rounded-xl bg-sky-500/10 dark:bg-sky-400/10"
            transition={{ type: 'spring', stiffness: 500, damping: 35 }}
          />
        )}
        <span className={`relative flex h-6 w-6 shrink-0 items-center justify-center ${
          active ? 'text-sky-600 dark:text-sky-400' : 'text-neutral-400 dark:text-neutral-500'
        }`}>
          {icon}
        </span>
        <span className="relative">{label}</span>
        {active && (
          <span className="relative ml-auto h-1.5 w-1.5 rounded-full bg-sky-500 dark:bg-sky-400" />
        )}
      </Link>
    )
  }

  const roleBadge: Record<string, string> = {
    super_admin: 'bg-violet-100 text-violet-600 dark:bg-violet-500/15 dark:text-violet-400',
    admin:       'bg-sky-100 text-sky-600 dark:bg-sky-500/15 dark:text-sky-400',
    analyst:     'bg-amber-100 text-amber-600 dark:bg-amber-500/15 dark:text-amber-400',
    researcher:  'bg-emerald-100 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-400',
    viewer:      'bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400',
  }
  const roleLabel = (user?.role ?? 'viewer').replace('_', ' ')
  const initials  = (user?.name ?? user?.email ?? 'R').slice(0, 2).toUpperCase()

  return (
    <div className="flex h-screen bg-[#F0F9FF] dark:bg-[#071521] transition-colors duration-300">
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* ── Sidebar ─────────────────────────────────────────────────────── */}
      <aside className={`
        fixed lg:relative z-50 flex h-full w-60 flex-col
        bg-white dark:bg-[#0A1929]
        border-r border-neutral-200/60 dark:border-white/[0.06]
        transition-transform duration-300
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>

        {/* Logo */}
        <div className="flex h-14 shrink-0 items-center gap-3 border-b border-neutral-200/60 px-4 dark:border-white/[0.06]">
          <Link to="/dashboard" className="flex min-w-0 flex-1 items-center gap-2.5">
            {/* Logo mark */}
            <div className="relative shrink-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-400 via-sky-500 to-violet-600 shadow-lg shadow-sky-500/30 ring-1 ring-white/10">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  {/* Text lines — NLP / document analysis */}
                  <rect x="3" y="4.5" width="14" height="2" rx="1" fill="white"/>
                  <rect x="3" y="9" width="10" height="2" rx="1" fill="white" fillOpacity="0.80"/>
                  <rect x="3" y="13.5" width="12" height="2" rx="1" fill="white" fillOpacity="0.60"/>
                  {/* Spark accent — top-right corner */}
                  <circle cx="15.5" cy="4" r="1.8" fill="white" fillOpacity="0.25"/>
                  <circle cx="15.5" cy="4" r="1.1" fill="white"/>
                </svg>
              </div>
              {/* Subtle outer glow ring */}
              <div className="pointer-events-none absolute inset-0 rounded-xl ring-1 ring-inset ring-sky-400/20" />
            </div>

            {/* Wordmark */}
            <div className="min-w-0 leading-none">
              <p className="text-[13.5px] font-black tracking-tight text-neutral-900 dark:text-white">
                Som<span className="bg-gradient-to-r from-sky-500 to-violet-500 bg-clip-text text-transparent">NLP</span>
              </p>
              <p className="mt-0.5 text-[9.5px] font-semibold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
                Research Platform
              </p>
            </div>
          </Link>
          <button onClick={() => setMobileOpen(false)} className="ml-auto shrink-0 rounded-lg p-1 text-neutral-400 hover:text-neutral-600 lg:hidden">
            <X size={16} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-2.5 py-4">
          <p className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-600">
            Navigation
          </p>
          <div className="space-y-0.5">
            {mainNav.map(item => <NavItem key={item.path} {...item} />)}
          </div>

          {adminUser && (
            <div className="mt-5">
              <div className="mb-1.5 mt-1 h-px bg-neutral-100 dark:bg-white/[0.05]" />
              <button
                onClick={() => setAdminExpanded(v => !v)}
                className={`mt-2 flex w-full items-center justify-between px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest transition-colors ${
                  isAdminSection
                    ? 'text-sky-600 dark:text-sky-400'
                    : 'text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300'
                }`}
              >
                <span className="flex items-center gap-1.5">
                  <Shield size={11} /> Admin
                </span>
                <motion.span
                  animate={{ rotate: adminExpanded || isAdminSection ? 0 : -90 }}
                  transition={{ duration: 0.15 }}
                >
                  <ChevronDown size={11} />
                </motion.span>
              </button>
              <AnimatePresence initial={false}>
                {(adminExpanded || isAdminSection) && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-0.5 space-y-0.5">
                      {adminNav.map(item => <NavItem key={item.path} {...item} />)}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="shrink-0 border-t border-neutral-200/60 px-2.5 py-3 dark:border-white/[0.06]">
          {/* User row */}
          <div className="flex items-center gap-2.5 rounded-xl px-3 py-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sky-500 text-[11px] font-black text-white">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-[12px] font-bold text-neutral-800 dark:text-neutral-200 leading-tight">
                {user?.name || user?.email || 'Researcher'}
              </p>
              <span className={`mt-0.5 inline-block rounded px-1.5 py-0.5 text-[9px] font-bold capitalize ${roleBadge[user?.role ?? 'viewer']}`}>
                {roleLabel}
              </span>
            </div>
            <button
              onClick={toggleTheme}
              aria-label="Toggle theme"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-neutral-400 transition-colors hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-white/8 dark:hover:text-neutral-200"
            >
              {theme === 'dark' ? <Sun size={13} /> : <Moon size={13} />}
            </button>
          </div>

          {/* Logout */}
          <button
            onClick={logout}
            className="mt-1 flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-[13px] font-semibold text-neutral-500 transition-colors hover:bg-red-50 hover:text-red-600 dark:text-neutral-500 dark:hover:bg-red-500/8 dark:hover:text-red-400"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Content ──────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar */}
        <header className="flex h-14 shrink-0 items-center border-b border-neutral-200/60 bg-white/90 px-5 backdrop-blur-sm dark:border-white/[0.06] dark:bg-[#0A1929]/90 z-30">
          <button
            onClick={() => setMobileOpen(true)}
            className="mr-3 rounded-lg p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-white/8 lg:hidden"
          >
            <Menu size={18} />
          </button>

          <p className="text-sm font-semibold text-neutral-700 dark:text-neutral-300">
            {[...mainNav, ...adminNav].find(n => isActive(n.path))?.label ?? 'Dashboard'}
          </p>

          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-[11px] font-medium text-neutral-400 dark:text-neutral-500 sm:block">
              {new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
            </span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto bg-[#F0F9FF] dark:bg-[#071521]">
          <div className="mx-auto w-full max-w-[1440px] p-6 lg:p-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}
