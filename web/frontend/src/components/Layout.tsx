import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import {
  Menu, X, BarChart3, Brain, Zap, LogOut, User as UserIcon,
  FlaskConical, LineChart, Users, ScrollText, ChevronDown, ChevronRight, Shield,
  Sun, Moon,
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '@hooks/useAuth'
import { isAdmin } from '@/types/auth'
import { useTheme } from '@/contexts/ThemeContext'

/* ── nav color configs ──────────────────────────────────────────────── */
const navColors: Record<string, { icon: string; active: string; indicator: string }> = {
  '/':            { icon: 'text-sky-500 bg-sky-50 dark:bg-sky-500/10',        active: 'text-sky-700 bg-sky-50/80 dark:text-sky-400 dark:bg-sky-500/10',       indicator: 'from-sky-500 to-blue-500' },
  '/predict':     { icon: 'text-primary-600 bg-primary-50 dark:bg-primary-500/10', active: 'text-primary-700 bg-primary-50/80 dark:text-primary-400 dark:bg-primary-500/10', indicator: 'from-sky-500 to-blue-500' },
  '/models':      { icon: 'text-amber-600 bg-amber-50 dark:bg-amber-500/10',  active: 'text-amber-700 bg-amber-50/80 dark:text-amber-400 dark:bg-amber-500/10',   indicator: 'from-amber-400 to-orange-500' },
  '/experiments': { icon: 'text-violet-600 bg-violet-50 dark:bg-violet-500/10', active: 'text-violet-700 bg-violet-50/80 dark:text-violet-400 dark:bg-violet-500/10', indicator: 'from-violet-500 to-purple-500' },
  '/analytics':   { icon: 'text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10', active: 'text-emerald-700 bg-emerald-50/80 dark:text-emerald-400 dark:bg-emerald-500/10', indicator: 'from-emerald-500 to-teal-500' },
  '/admin/users': { icon: 'text-rose-600 bg-rose-50 dark:bg-rose-500/10',     active: 'text-rose-700 bg-rose-50/80 dark:text-rose-400 dark:bg-rose-500/10',     indicator: 'from-rose-500 to-pink-500' },
  '/admin/logs':  { icon: 'text-neutral-600 bg-neutral-100 dark:bg-neutral-800', active: 'text-neutral-700 bg-neutral-100/80 dark:text-neutral-300 dark:bg-neutral-800', indicator: 'from-neutral-400 to-neutral-500' },
}

export const Layout = () => {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [adminExpanded, setAdminExpanded] = useState(false)
  const location = useLocation()
  const { user, logout } = useAuth()
  const adminUser = isAdmin(user)
  const { theme, toggleTheme } = useTheme()

  const mainNav = [
    { path: '/', icon: <BarChart3 size={16} />, label: 'Dashboard' },
    { path: '/predict', icon: <Brain size={16} />, label: 'Predict' },
    { path: '/models', icon: <Zap size={16} />, label: 'Models' },
    { path: '/experiments', icon: <FlaskConical size={16} />, label: 'Experiments' },
  ]
  const adminNav = [
    { path: '/analytics', icon: <LineChart size={16} />, label: 'Analytics' },
    { path: '/admin/users', icon: <Users size={16} />, label: 'Users' },
    { path: '/admin/logs', icon: <ScrollText size={16} />, label: 'Audit Logs' },
  ]

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path)
  const isAdminSection = adminNav.some((item) => location.pathname.startsWith(item.path))

  const NavItem = ({ path, icon, label }: { path: string; icon: React.ReactNode; label: string }) => {
    const active = isActive(path)
    const c = navColors[path] ?? navColors['/admin/logs']
    return (
      <Link
        to={path}
        onClick={() => setMobileOpen(false)}
        className={`
          group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all duration-200
          ${active ? c.active : 'text-neutral-500 hover:bg-neutral-50 hover:text-neutral-800 dark:text-neutral-400 dark:hover:bg-neutral-800/40 dark:hover:text-neutral-100'}
        `}
      >
        {active && (
          <motion.div
            layoutId="activeNavBar"
            className={`absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-gradient-to-b ${c.indicator}`}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          />
        )}
        {/* Colored icon box */}
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition-all duration-200 ${
          active ? c.icon : 'text-neutral-400 bg-transparent group-hover:bg-neutral-100 dark:group-hover:bg-neutral-800'
        }`}>
          {icon}
        </span>
        <span className="tracking-tight">{label}</span>
      </Link>
    )
  }

  const roleBadgeColor: Record<string, string> = {
    super_admin: 'bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400',
    admin: 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',
    analyst: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
    researcher: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
    viewer: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400',
  }
  const roleLabel = (user?.role ?? 'viewer').replace('_', ' ')

  return (
    <div className="flex h-screen bg-[#F0F9FF] dark:bg-[#071521] transition-colors duration-300">
      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden" onClick={() => setMobileOpen(false)} />
      )}

      {/* ── Sidebar ───────────────────────────────────────────────────── */}
      <aside className={`
        fixed lg:relative z-50 h-full w-64 flex flex-col
        bg-white dark:bg-[#0D2137]
        border-r border-sky-100 dark:border-sky-900/40
        transition-transform duration-300
        ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        {/* Logo */}
        <div className="flex items-center justify-between px-4 py-5 border-b border-sky-100 dark:border-sky-900/40 shrink-0">
          <Link to="/" className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-sky-600 shadow-lg shadow-sky-500/30">
              <span className="text-[17px] font-black text-white">S</span>
            </div>
            <div>
              <span className="block text-[15px] font-extrabold tracking-tight text-neutral-900 dark:text-white">SNLP</span>
              <span className="block text-[10px] font-semibold text-neutral-400 dark:text-neutral-500 tracking-wider uppercase">Research</span>
            </div>
          </Link>
          <button onClick={() => setMobileOpen(false)} className="lg:hidden rounded-lg p-1 text-neutral-400 hover:text-neutral-700">
            <X size={18} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
          <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-600">Main</p>
          {mainNav.map((item) => <NavItem key={item.path} {...item} />)}

          {/* Admin section */}
          {adminUser && (
            <div className="mt-5">
              <button
                onClick={() => setAdminExpanded((v) => !v)}
                className={`w-full flex items-center justify-between px-3 py-1.5 mb-1 text-[10px] font-bold uppercase tracking-widest transition-colors
                  ${isAdminSection ? 'text-primary-600 dark:text-primary-400' : 'text-neutral-400 dark:text-neutral-500 hover:text-neutral-600 dark:hover:text-neutral-300'}
                `}
              >
                <span className="flex items-center gap-1.5">
                  <Shield size={12} />
                  Admin
                </span>
                {adminExpanded || isAdminSection ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </button>

              <AnimatePresence initial={false}>
                {(adminExpanded || isAdminSection) && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden space-y-0.5"
                  >
                    {adminNav.map((item) => <NavItem key={item.path} {...item} />)}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </nav>

        {/* User footer */}
        <div className="px-3 pb-4 border-t border-sky-100 dark:border-sky-900/40 shrink-0 pt-3 space-y-1">
          <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-sky-50/60 dark:bg-sky-900/20">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary-100 dark:bg-primary-500/10 text-primary-600 dark:text-primary-400">
              <UserIcon size={14} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-bold text-neutral-800 dark:text-neutral-200 leading-tight">
                {user?.name || user?.email || 'Researcher'}
              </p>
              <span className={`mt-0.5 inline-block rounded-md px-1.5 py-0.5 text-[9px] font-bold capitalize ${roleBadgeColor[user?.role ?? 'viewer']}`}>
                {roleLabel}
              </span>
            </div>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-500/10 transition-colors group"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-rose-50 dark:bg-rose-500/10 group-hover:bg-rose-100 dark:group-hover:bg-rose-500/20 transition-colors">
              <LogOut size={14} />
            </span>
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Content ────────────────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center border-b border-sky-100/80 bg-white/85 px-5 backdrop-blur-md dark:border-sky-900/40 dark:bg-[#0D2137]/90 z-30">
          <button
            onClick={() => setMobileOpen(true)}
            className="lg:hidden mr-3 rounded-lg p-1.5 text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          >
            <Menu size={20} />
          </button>

          {/* Page title */}
          <div className="flex items-center gap-2 text-sm">
            <span className="font-bold text-neutral-800 dark:text-neutral-200">
              {[...mainNav, ...adminNav].find((n) => isActive(n.path))?.label ?? 'Dashboard'}
            </span>
          </div>

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="ml-auto flex h-9 w-9 items-center justify-center rounded-xl border border-neutral-200/70 bg-white text-neutral-500 shadow-sm transition-all hover:border-primary-300 hover:text-primary-600 dark:border-neutral-700/70 dark:bg-neutral-800 dark:text-neutral-400 dark:hover:border-primary-500/50 dark:hover:text-primary-400"
          >
            <AnimatePresence mode="wait" initial={false}>
              {theme === 'dark' ? (
                <motion.span key="sun" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.2 }}>
                  <Sun size={16} />
                </motion.span>
              ) : (
                <motion.span key="moon" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.2 }}>
                  <Moon size={16} />
                </motion.span>
              )}
            </AnimatePresence>
          </button>
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
