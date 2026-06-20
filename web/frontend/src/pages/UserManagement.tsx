import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Users, Search, Plus, RefreshCw, ChevronLeft, ChevronRight,
  MoreHorizontal, ShieldOff, ShieldCheck, Trash2, KeyRound, X, Check,
} from 'lucide-react'
import {
  listUsers, createUser, deleteUser, suspendUser,
  activateUser, resetPassword,
} from '@services/adminService'
import type { AdminUser, CreateUserPayload } from '@services/adminService'
import { getApiErrorMessage } from '@services/api'
import type { UserRole } from '@/types/auth'
import { useAuth } from '@hooks/useAuth'

const ROLES: UserRole[] = ['super_admin', 'admin', 'analyst', 'researcher', 'viewer']

const roleBadge: Record<string, string> = {
  super_admin: 'bg-violet-100 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400',
  admin: 'bg-blue-100 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',
  analyst: 'bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400',
  researcher: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400',
  viewer: 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400',
}

const fmt = (d: string | null) =>
  d ? new Date(d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

// ── Create User Modal ──────────────────────────────────────────────────────────

interface CreateModalProps {
  onClose: () => void
  onSuccess: () => void
}

function CreateModal({ onClose, onSuccess }: CreateModalProps) {
  const [form, setForm] = useState<CreateUserPayload>({
    email: '', name: '', password: '', role: 'viewer',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const submit = async () => {
    if (!form.email || !form.password) return
    setSaving(true)
    setError(null)
    try {
      await createUser(form)
      onSuccess()
      onClose()
    } catch (e) {
      setError(getApiErrorMessage(e, 'Failed to create user.'))
    } finally {
      setSaving(false)
    }
  }

  const field = (
    label: string,
    key: keyof CreateUserPayload,
    type = 'text',
    placeholder = ''
  ) => (
    <div>
      <label className="mb-1.5 block text-xs font-semibold text-neutral-600 dark:text-neutral-400">{label}</label>
      <input
        type={type}
        value={form[key] as string}
        placeholder={placeholder}
        onChange={(e) => setForm((p) => ({ ...p, [key]: e.target.value }))}
        className="h-10 w-full rounded-xl border border-neutral-200 bg-white px-3 text-sm text-neutral-900 placeholder-neutral-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white dark:placeholder-neutral-500"
      />
    </div>
  )

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl dark:bg-neutral-900 dark:border dark:border-neutral-800"
      >
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-bold text-neutral-900 dark:text-white">Create User</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200">
            <X size={18} />
          </button>
        </div>

        <div className="space-y-4">
          {field('Full Name', 'name', 'text', 'Jane Doe')}
          {field('Email', 'email', 'email', 'jane@example.com')}
          {field('Password', 'password', 'password', '••••••••')}
          <div>
            <label className="mb-1.5 block text-xs font-semibold text-neutral-600 dark:text-neutral-400">Role</label>
            <select
              value={form.role}
              onChange={(e) => setForm((p) => ({ ...p, role: e.target.value as UserRole }))}
              className="h-10 w-full rounded-xl border border-neutral-200 bg-white px-3 text-sm text-neutral-900 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r.replace('_', ' ')}</option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <p className="mt-3 rounded-xl border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-700 dark:border-red-800/40 dark:bg-red-900/20 dark:text-red-400">
            {error}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button onClick={onClose} className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800 transition-colors">
            Cancel
          </button>
          <button
            onClick={submit}
            disabled={saving || !form.email || !form.password}
            className="flex items-center gap-2 rounded-xl bg-primary-600 px-5 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
          >
            {saving ? <RefreshCw size={14} className="animate-spin" /> : <Check size={14} />}
            Create
          </button>
        </div>
      </motion.div>
    </div>
  )
}

// ── Reset Password Modal ───────────────────────────────────────────────────────

interface ResetModalProps {
  user: AdminUser
  onClose: () => void
}

function ResetModal({ user, onClose }: ResetModalProps) {
  const [pw, setPw] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState(false)

  const submit = async () => {
    if (pw.length < 8) return
    setSaving(true)
    setError(null)
    try {
      await resetPassword(user.id, pw)
      setDone(true)
    } catch (e) {
      setError(getApiErrorMessage(e, 'Failed to reset password.'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        exit={{ opacity: 0, scale: 0.96 }}
        className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl dark:bg-neutral-900 dark:border dark:border-neutral-800"
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-bold text-neutral-900 dark:text-white">Reset Password</h2>
          <button onClick={onClose} className="rounded-lg p-1 text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-200">
            <X size={18} />
          </button>
        </div>
        <p className="mb-4 text-xs text-neutral-500 dark:text-neutral-400">
          Setting a new password for <span className="font-semibold">{user.email}</span>
        </p>
        {done ? (
          <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:bg-emerald-900/20 dark:text-emerald-400">
            Password updated successfully.
          </div>
        ) : (
          <>
            <input
              type="password"
              placeholder="New password (min 8 chars)"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              className="h-10 w-full rounded-xl border border-neutral-200 bg-white px-3 text-sm text-neutral-900 placeholder-neutral-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
            />
            {error && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{error}</p>}
            <div className="mt-5 flex justify-end gap-3">
              <button onClick={onClose} className="rounded-xl border border-neutral-200 px-4 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:text-neutral-300 dark:hover:bg-neutral-800 transition-colors">
                Cancel
              </button>
              <button
                onClick={submit}
                disabled={saving || pw.length < 8}
                className="flex items-center gap-2 rounded-xl bg-primary-600 px-5 py-2 text-sm font-semibold text-white hover:bg-primary-700 disabled:opacity-50 transition-colors"
              >
                {saving ? <RefreshCw size={14} className="animate-spin" /> : <KeyRound size={14} />}
                Reset
              </button>
            </div>
          </>
        )}
      </motion.div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

export default function UserManagement() {
  const { user: me } = useAuth()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [pages, setPages] = useState(1)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null)
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  const isSuperAdmin = me?.role === 'super_admin'

  const load = useCallback(async (p = page) => {
    setLoading(true)
    setError(null)
    try {
      const res = await listUsers({
        page: p, limit: 20,
        search: search || undefined,
        role: roleFilter || undefined,
        status: statusFilter || undefined,
      })
      setUsers(res.data.users)
      setTotal(res.data.total)
      setPages(res.data.pages)
    } catch (e) {
      setError(getApiErrorMessage(e, 'Failed to load users.'))
    } finally {
      setLoading(false)
    }
  }, [page, search, roleFilter, statusFilter])

  useEffect(() => { load() }, [load])

  const handleToggle = async (u: AdminUser) => {
    try {
      if (u.is_active) await suspendUser(u.id)
      else await activateUser(u.id)
      load()
    } catch {}
    setMenuOpen(null)
  }

  const handleDelete = async (u: AdminUser) => {
    if (!confirm(`Delete ${u.email}? This cannot be undone.`)) return
    try {
      await deleteUser(u.id)
      load()
    } catch {}
    setMenuOpen(null)
  }

  return (
    <div className="space-y-6" onClick={() => setMenuOpen(null)}>
      {/* Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tight text-neutral-900 dark:text-white">Users</h1>
          <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
            {total.toLocaleString()} registered accounts
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 rounded-xl bg-primary-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-primary-700 transition-colors shadow-sm"
        >
          <Plus size={16} />
          Create User
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search by email or name…"
            className="h-10 w-full rounded-xl border border-neutral-200 bg-white pl-9 pr-4 text-sm text-neutral-900 placeholder-neutral-400 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white dark:placeholder-neutral-500"
          />
        </div>
        <select
          value={roleFilter}
          onChange={(e) => { setRoleFilter(e.target.value); setPage(1) }}
          className="h-10 rounded-xl border border-neutral-200 bg-white px-3 text-sm text-neutral-700 focus:border-primary-500 focus:outline-none dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
        >
          <option value="">All roles</option>
          {ROLES.map((r) => <option key={r} value={r}>{r.replace('_', ' ')}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
          className="h-10 rounded-xl border border-neutral-200 bg-white px-3 text-sm text-neutral-700 focus:border-primary-500 focus:outline-none dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300"
        >
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
        <button
          onClick={() => load()}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-neutral-200 bg-white text-neutral-500 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-400 transition-colors"
        >
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700 dark:border-red-800/50 dark:bg-red-900/20 dark:text-red-400">
          {error}
        </div>
      )}

      {/* Table */}
      <div className="overflow-hidden rounded-2xl border border-neutral-200/60 bg-white dark:border-neutral-800/60 dark:bg-neutral-900">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-100 bg-neutral-50/80 dark:border-neutral-800 dark:bg-neutral-800/30">
                <th className="px-5 py-3 text-left text-xs font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">User</th>
                <th className="px-5 py-3 text-left text-xs font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Role</th>
                <th className="px-5 py-3 text-left text-xs font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Status</th>
                <th className="px-5 py-3 text-left text-xs font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Predictions</th>
                <th className="px-5 py-3 text-left text-xs font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Last Login</th>
                <th className="px-5 py-3 text-left text-xs font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Joined</th>
                <th className="px-5 py-3 w-12" />
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100 dark:divide-neutral-800">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(7)].map((_, j) => (
                      <td key={j} className="px-5 py-4">
                        <div className="h-4 animate-pulse rounded bg-neutral-100 dark:bg-neutral-800" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-10 text-center text-sm text-neutral-400">
                    <Users size={32} className="mx-auto mb-3 text-neutral-300 dark:text-neutral-600" />
                    No users found
                  </td>
                </tr>
              ) : (
                users.map((u) => (
                  <motion.tr
                    key={u.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="group hover:bg-neutral-50/60 dark:hover:bg-neutral-800/30 transition-colors"
                  >
                    <td className="px-5 py-4">
                      <div>
                        <p className="font-semibold text-neutral-900 dark:text-white">{u.name || '—'}</p>
                        <p className="text-xs text-neutral-500 dark:text-neutral-400">{u.email}</p>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-block rounded-lg px-2 py-0.5 text-xs font-bold capitalize ${roleBadge[u.role]}`}>
                        {u.role.replace('_', ' ')}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold ${u.is_active ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400' : 'bg-red-50 text-red-600 dark:bg-red-500/10 dark:text-red-400'}`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? 'bg-emerald-400' : 'bg-red-400'}`} />
                        {u.is_active ? 'Active' : 'Suspended'}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-xs text-neutral-600 dark:text-neutral-400 font-mono">
                      {u.daily_prediction_count}/{u.daily_prediction_limit === -1 ? '∞' : u.daily_prediction_limit}
                    </td>
                    <td className="px-5 py-4 text-xs text-neutral-500 dark:text-neutral-400">{fmt(u.last_login)}</td>
                    <td className="px-5 py-4 text-xs text-neutral-500 dark:text-neutral-400">{fmt(u.created_at)}</td>
                    <td className="px-5 py-4 relative" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => setMenuOpen(menuOpen === u.id ? null : u.id)}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-neutral-400 hover:bg-neutral-100 hover:text-neutral-700 dark:hover:bg-neutral-700 dark:hover:text-neutral-200 transition-colors"
                      >
                        <MoreHorizontal size={16} />
                      </button>
                      <AnimatePresence>
                        {menuOpen === u.id && (
                          <motion.div
                            initial={{ opacity: 0, scale: 0.95, y: -4 }}
                            animate={{ opacity: 1, scale: 1, y: 0 }}
                            exit={{ opacity: 0, scale: 0.95, y: -4 }}
                            className="absolute right-4 top-12 z-30 w-44 rounded-xl border border-neutral-200 bg-white py-1.5 shadow-xl dark:border-neutral-700 dark:bg-neutral-800"
                          >
                            <button
                              onClick={() => { handleToggle(u) }}
                              className="flex w-full items-center gap-2.5 px-4 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 dark:text-neutral-300 dark:hover:bg-neutral-700/50 transition-colors"
                            >
                              {u.is_active ? <ShieldOff size={14} /> : <ShieldCheck size={14} />}
                              {u.is_active ? 'Suspend' : 'Activate'}
                            </button>
                            <button
                              onClick={() => { setResetTarget(u); setMenuOpen(null) }}
                              className="flex w-full items-center gap-2.5 px-4 py-2 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 dark:text-neutral-300 dark:hover:bg-neutral-700/50 transition-colors"
                            >
                              <KeyRound size={14} />
                              Reset Password
                            </button>
                            {isSuperAdmin && u.id !== me?.id && (
                              <button
                                onClick={() => handleDelete(u)}
                                className="flex w-full items-center gap-2.5 px-4 py-2 text-xs font-semibold text-red-600 hover:bg-red-50 dark:text-red-400 dark:hover:bg-red-900/20 transition-colors"
                              >
                                <Trash2 size={14} />
                                Delete
                              </button>
                            )}
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {pages > 1 && (
          <div className="flex items-center justify-between border-t border-neutral-100 px-5 py-3 dark:border-neutral-800">
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Page {page} of {pages} · {total} users
            </p>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 text-neutral-500 hover:bg-neutral-50 disabled:opacity-40 dark:border-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-800 transition-colors"
              >
                <ChevronLeft size={15} />
              </button>
              <button
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                disabled={page >= pages}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 text-neutral-500 hover:bg-neutral-50 disabled:opacity-40 dark:border-neutral-700 dark:text-neutral-400 dark:hover:bg-neutral-800 transition-colors"
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Modals */}
      <AnimatePresence>
        {showCreate && (
          <CreateModal
            onClose={() => setShowCreate(false)}
            onSuccess={load}
          />
        )}
        {resetTarget && (
          <ResetModal
            user={resetTarget}
            onClose={() => setResetTarget(null)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
