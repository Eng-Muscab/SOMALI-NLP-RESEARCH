import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import {
  Trophy, FlaskConical, Search, X, FileSpreadsheet,
  Download, ChevronRight, Layers, Brain, Cpu,
} from 'lucide-react'
import { listExperiments } from '../services/experimentService'
import { getApiErrorMessage } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import type { Experiment } from '../types/experiment'

/* ── Types ────────────────────────────────────────────────────────────────── */
interface ComparisonRow {
  experiment: string; family: string; model: string
  accuracy: number; precision: number; recall: number
  f1: number; macro_f1: number; test_rows: number
}

/* ── Constants ────────────────────────────────────────────────────────────── */
const EXP_META: Record<string, { short: string; label: string; gradient: string; badge: string }> = {
  experiment_1_stopwords_included: {
    short: 'Exp 1', label: 'Stopwords Included',
    gradient: 'from-violet-600 via-purple-600 to-indigo-700',
    badge: 'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300',
  },
  experiment_2_stopwords_removed: {
    short: 'Exp 2', label: 'Stopwords Removed',
    gradient: 'from-sky-600 via-cyan-600 to-teal-600',
    badge: 'bg-sky-100 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
  },
}

const FAMILY_META: Record<string, { label: string; color: string; dot: string; icon: typeof Layers }> = {
  traditional_ml: { label: 'Traditional ML', color: 'bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-400',   dot: 'bg-blue-500', icon: Layers },
  deep_learning:  { label: 'Deep Learning',  color: 'bg-orange-50 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400', dot: 'bg-orange-500', icon: Brain },
  transformers:   { label: 'Transformer',    color: 'bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-400', dot: 'bg-violet-500', icon: Cpu },
}

const downloadCSV = (items: Experiment[], name: string) => {
  if (!items.length) return
  const headers = ['Name', 'Date', 'Status', 'Accuracy', 'F1', 'Models', 'Dataset', 'Notes']
  const rows = items.map(i => [i.name, i.date, i.status, i.accuracy, i.f1, i.models, i.dataset ?? '', i.notes ?? ''].map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
  const blob = new Blob([[headers.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.setAttribute('download', `${name}.csv`)
  document.body.appendChild(a); a.click(); document.body.removeChild(a); URL.revokeObjectURL(url)
}

/* ── Sub-components ───────────────────────────────────────────────────────── */
function ExperimentCard({ exp, comparison, onClick }: {
  exp: Experiment
  comparison: ComparisonRow[]
  onClick: () => void
}) {
  const meta   = EXP_META[exp.id] ?? { short: exp.id, label: exp.name, gradient: 'from-neutral-600 to-neutral-800', badge: '' }
  const myRows = comparison.filter(r => r.experiment === exp.id)
  const famCounts = {
    traditional_ml: myRows.filter(r => r.family === 'traditional_ml').length,
    deep_learning:  myRows.filter(r => r.family === 'deep_learning').length,
    transformers:   myRows.filter(r => r.family === 'transformers').length,
  }
  const bestModel = (exp.params as Record<string, unknown>)?.best_model as string | undefined

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="group relative overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm transition-all duration-300 hover:shadow-lg dark:border-neutral-800/60 dark:bg-neutral-900"
    >
      {/* Gradient top bar */}
      <div className={`h-1.5 w-full bg-gradient-to-r ${meta.gradient}`} />

      <div className="p-6">
        {/* Header */}
        <div className="mb-4 flex items-start justify-between gap-3">
          <div>
            <span className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-widest ${meta.badge}`}>
              {meta.short}
            </span>
            <h3 className="mt-2 text-base font-extrabold leading-tight text-neutral-900 dark:text-white">
              {meta.label}
            </h3>
            <p className="mt-0.5 text-[11px] text-neutral-400 dark:text-neutral-500">{exp.date}</p>
          </div>
          <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${meta.gradient} shadow-md`}>
            <FlaskConical size={18} className="text-white" />
          </div>
        </div>

        {/* Key metrics */}
        <div className="mb-5 grid grid-cols-3 gap-3">
          {[
            { label: 'Best Acc.', value: `${exp.accuracy.toFixed(1)}%` },
            { label: 'Best F1',  value: exp.f1.toFixed(3) },
            { label: 'Models',   value: exp.models },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-xl bg-neutral-50 p-3 dark:bg-neutral-800/40">
              <p className="text-[9px] font-bold uppercase tracking-widest text-neutral-400">{label}</p>
              <p className="mt-0.5 text-sm font-black text-neutral-900 dark:text-white">{value}</p>
            </div>
          ))}
        </div>

        {/* Best model */}
        {bestModel && (
          <div className="mb-4 rounded-xl border border-neutral-100 bg-neutral-50/60 px-3.5 py-2.5 dark:border-neutral-800 dark:bg-neutral-800/20">
            <p className="text-[9px] font-bold uppercase tracking-widest text-neutral-400">Top Model</p>
            <p className="mt-0.5 text-xs font-bold text-neutral-700 dark:text-neutral-200">{bestModel}</p>
          </div>
        )}

        {/* Family breakdown */}
        <div className="mb-5 flex gap-2">
          {Object.entries(famCounts).map(([key, count]) => {
            const fm = FAMILY_META[key]
            return (
              <span key={key} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${fm.color}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${fm.dot}`} />
                {count}
              </span>
            )
          })}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <button onClick={onClick}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl bg-gradient-to-r ${meta.gradient} py-2.5 text-xs font-bold text-white shadow-sm transition-all hover:opacity-90`}>
            View Details <ChevronRight size={13} />
          </button>
          <button onClick={() => downloadCSV([exp], `experiment-${exp.id}`)}
            className="flex items-center gap-1.5 rounded-xl border border-neutral-200 bg-white px-3 py-2.5 text-xs font-bold text-neutral-600 transition-colors hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
            <Download size={13} />
          </button>
        </div>
      </div>
    </motion.div>
  )
}

/* ── Main Component ───────────────────────────────────────────────────────── */
export default function Experiments() {
  const [experiments, setExperiments]   = useState<Experiment[]>([])
  const [comparison, setComparison]     = useState<ComparisonRow[]>([])
  const [loading, setLoading]           = useState(true)
  const [cmpLoading, setCmpLoading]     = useState(true)
  const [loadError, setLoadError]       = useState<string | null>(null)
  const [selected, setSelected]         = useState<Experiment | null>(null)

  const [expTab, setExpTab]     = useState<'all' | string>('all')
  const [famTab, setFamTab]     = useState<'all' | string>('all')
  const [cmpSearch, setCmpSearch] = useState('')

  const { showToast } = useToast()

  const ALLOWED = ['experiment_1_stopwords_included', 'experiment_2_stopwords_removed']

  useEffect(() => {
    listExperiments()
      .then(r => setExperiments(r.data.filter(e => ALLOWED.includes(e.id)).sort((a, b) => a.id.localeCompare(b.id))))
      .catch(err => { const m = getApiErrorMessage(err, 'Unable to load experiments.'); setLoadError(m); showToast(m, 'error') })
      .finally(() => setLoading(false))

    import('../services/api').then(({ default: api }) =>
      api.get<ComparisonRow[]>('/experiments/comparison')
        .then(r => {
            const raw: ComparisonRow[] = Array.isArray(r.data) ? r.data : []
            const seen = new Set<string>()
            const deduped = raw.filter(row => {
              const key = `${row.experiment}::${row.model}`
              if (seen.has(key)) return false
              seen.add(key)
              return true
            })
            setComparison(deduped)
          })
        .catch(() => setComparison([]))
        .finally(() => setCmpLoading(false))
    )
  }, [showToast])

  const filteredCmp = useMemo(() => comparison.filter(r => {
    const eOk = expTab === 'all' || r.experiment === expTab
    const fOk = famTab === 'all' || r.family === famTab
    const sOk = !cmpSearch.trim() || r.model.toLowerCase().includes(cmpSearch.toLowerCase())
    return eOk && fOk && sOk
  }), [comparison, expTab, famTab, cmpSearch])

  /* Bar chart data — top 10 models by accuracy */
  const barData = useMemo(() =>
    filteredCmp.slice(0, 12).map(r => ({
      name: r.model.replace(/_/g, ' ').slice(0, 18),
      accuracy: r.accuracy,
      exp: r.experiment.includes('1') ? 'Exp 1' : 'Exp 2',
    })).reverse(),
    [filteredCmp])

  const cardCls = 'overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900'

  return (
    <div className="space-y-6 pb-12">

      {/* ── Hero ─────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-violet-600 via-purple-700 to-indigo-800 px-7 py-7 text-white shadow-xl"
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-white/5 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-10 left-1/3 h-40 w-40 rounded-full bg-violet-300/10 blur-3xl" />
        <div className="relative flex items-center justify-between gap-4">
          <div>
            <div className="mb-2.5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-violet-200">
              <FlaskConical size={12} /> Somali NLP Research
            </div>
            <h1 className="text-[1.75rem] font-extrabold tracking-tight">Experiments</h1>
            <p className="mt-1 text-sm text-violet-200/90">
              {loading ? 'Loading…' : `${experiments.length} ablation experiments · ${comparison.length} model evaluations`}
            </p>
          </div>
          {!loading && (
            <div className="hidden sm:flex items-center gap-2 rounded-2xl bg-white/10 px-4 py-2.5">
              <Trophy size={14} className="text-amber-300" />
              <span className="text-sm font-bold">{comparison.length} models ranked</span>
            </div>
          )}
        </div>
      </motion.div>

      {/* ── Error ────────────────────────────────────────────────────── */}
      {loadError && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
          {loadError}
        </div>
      )}

      {/* ── Experiment Cards ─────────────────────────────────────────── */}
      {loading ? (
        <div className="grid gap-6 sm:grid-cols-2">
          {[0, 1].map(i => (
            <div key={i} className={`${cardCls} h-72 animate-pulse`}>
              <div className="h-1.5 w-full bg-neutral-200 dark:bg-neutral-700" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2">
          {experiments.map(exp => (
            <ExperimentCard key={exp.id} exp={exp} comparison={comparison} onClick={() => setSelected(exp)} />
          ))}
        </div>
      )}

      {/* ── Model Leaderboard ────────────────────────────────────────── */}
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className={cardCls}>

        {/* Header */}
        <div className="flex flex-col gap-4 border-b border-neutral-100 px-6 py-5 dark:border-neutral-800 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-md shadow-orange-500/20">
              <Trophy size={18} className="text-white" />
            </div>
            <div>
              <h2 className="text-base font-extrabold text-neutral-900 dark:text-white">Model Leaderboard</h2>
              <p className="text-[11px] text-neutral-400 dark:text-neutral-500">
                All models ranked by accuracy across both experiments
              </p>
            </div>
          </div>
          <div className="relative w-full sm:w-52">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-neutral-400" />
            <input value={cmpSearch} onChange={e => setCmpSearch(e.target.value)} placeholder="Search model…"
              className="h-9 w-full rounded-xl border border-neutral-200 bg-neutral-50 pl-8 pr-3 text-xs font-semibold text-neutral-800 placeholder-neutral-400 focus:border-primary-400 focus:bg-white focus:outline-none dark:border-neutral-700 dark:bg-neutral-800 dark:text-white" />
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 border-b border-neutral-100 px-6 py-3 dark:border-neutral-800">
          {/* Experiment tabs */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">Experiment:</span>
            {[
              { key: 'all', label: 'Both' },
              { key: 'experiment_1_stopwords_included', label: 'Exp 1 — Stopwords Included' },
              { key: 'experiment_2_stopwords_removed',  label: 'Exp 2 — Stopwords Removed' },
            ].map(({ key, label }) => (
              <button key={key} onClick={() => setExpTab(key)}
                className={`rounded-full px-3 py-1 text-[11px] font-bold transition-all ${
                  expTab === key
                    ? 'bg-violet-600 text-white shadow-sm'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700'
                }`}>
                {label}
              </button>
            ))}
          </div>
          <div className="h-4 w-px bg-neutral-200 dark:bg-neutral-700" />
          {/* Family tabs */}
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">Family:</span>
            {[
              { key: 'all', label: 'All' },
              { key: 'traditional_ml', label: 'Traditional ML' },
              { key: 'deep_learning',  label: 'Deep Learning' },
              { key: 'transformers',   label: 'Transformer' },
            ].map(({ key, label }) => (
              <button key={key} onClick={() => setFamTab(key)}
                className={`rounded-full px-3 py-1 text-[11px] font-bold transition-all ${
                  famTab === key
                    ? 'bg-amber-500 text-white shadow-sm'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300 dark:hover:bg-neutral-700'
                }`}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Bar chart — top models */}
        {!cmpLoading && filteredCmp.length > 0 && (
          <div className="border-b border-neutral-100 px-6 py-4 dark:border-neutral-800">
            <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-neutral-400">Accuracy Overview (top 12)</p>
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData} layout="vertical" margin={{ top: 0, right: 40, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.08)" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 10 }} stroke="rgba(148,163,184,0.4)" tickFormatter={v => `${v}%`} />
                  <YAxis type="category" dataKey="name" tick={{ fontSize: 9 }} width={110} stroke="rgba(148,163,184,0.4)" />
                  <Tooltip formatter={(v: number) => `${v.toFixed(2)}%`} contentStyle={{ fontSize: 12, borderRadius: 10 }} />
                  <Bar dataKey="accuracy" radius={[0, 4, 4, 0]}
                    fill="url(#accGrad)"
                  />
                  <defs>
                    <linearGradient id="accGrad" x1="0" y1="0" x2="1" y2="0">
                      <stop offset="0%" stopColor="#8b5cf6" />
                      <stop offset="100%" stopColor="#06b6d4" />
                    </linearGradient>
                  </defs>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-left text-sm">
            <thead>
              <tr className="border-b border-neutral-100 dark:border-neutral-800">
                {['#', 'Model', 'Experiment', 'Family', 'Accuracy', 'F1', 'Precision', 'Recall'].map(h => (
                  <th key={h} className="px-5 py-3.5 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50 dark:divide-neutral-800/40">
              {cmpLoading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <tr key={i}>
                    {Array.from({ length: 8 }).map((_, j) => (
                      <td key={j} className="px-5 py-3.5">
                        <div className="h-4 w-full animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : filteredCmp.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-5 py-14 text-center">
                    <div className="flex flex-col items-center gap-2 text-neutral-400">
                      <Trophy size={28} className="text-neutral-200 dark:text-neutral-700" />
                      <p className="text-sm font-semibold">No models match the current filters.</p>
                    </div>
                  </td>
                </tr>
              ) : filteredCmp.map((row, idx) => {
                const globalRank = comparison.findIndex(r => r.model === row.model && r.experiment === row.experiment) + 1
                const fam  = FAMILY_META[row.family] ?? { label: row.family, color: 'bg-neutral-100 text-neutral-600', dot: 'bg-neutral-400' }
                const exp  = EXP_META[row.experiment] ?? { short: row.experiment, badge: 'bg-neutral-100 text-neutral-600' }
                const medal = globalRank === 1 ? '🥇' : globalRank === 2 ? '🥈' : globalRank === 3 ? '🥉' : null
                const isTop3 = globalRank <= 3

                return (
                  <motion.tr key={`${row.experiment}-${row.model}`}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: Math.min(idx * 0.015, 0.3) }}
                    className={`transition-colors hover:bg-neutral-50/80 dark:hover:bg-neutral-800/20 ${isTop3 ? 'bg-amber-50/40 dark:bg-amber-500/5' : ''}`}
                  >
                    {/* Rank */}
                    <td className="w-10 px-5 py-3.5 text-center">
                      {medal
                        ? <span className="text-lg leading-none">{medal}</span>
                        : <span className="text-xs font-bold text-neutral-400 dark:text-neutral-500">#{globalRank}</span>}
                    </td>

                    {/* Model */}
                    <td className="px-5 py-3.5">
                      <span className={`text-sm font-bold ${isTop3 ? 'text-neutral-900 dark:text-white' : 'text-neutral-700 dark:text-neutral-300'}`}>
                        {row.model}
                      </span>
                    </td>

                    {/* Experiment */}
                    <td className="px-5 py-3.5">
                      <span className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-extrabold uppercase tracking-wide ${exp.badge}`}>
                        {exp.short}
                      </span>
                    </td>

                    {/* Family */}
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-bold ${fam.color}`}>
                        <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${fam.dot}`} />
                        {fam.label}
                      </span>
                    </td>

                    {/* Accuracy with bar */}
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2.5">
                        <span className="w-14 text-right font-mono text-xs font-black text-neutral-800 dark:text-neutral-200">
                          {row.accuracy.toFixed(2)}%
                        </span>
                        <div className="relative h-2 w-20 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${row.accuracy}%` }}
                            transition={{ duration: 0.7, ease: 'easeOut', delay: idx * 0.02 }}
                            className={`absolute inset-y-0 left-0 rounded-full ${
                              row.accuracy >= 90 ? 'bg-gradient-to-r from-emerald-500 to-teal-400'
                              : row.accuracy >= 80 ? 'bg-gradient-to-r from-violet-500 to-indigo-400'
                              : 'bg-gradient-to-r from-amber-400 to-orange-400'
                            }`}
                          />
                        </div>
                      </div>
                    </td>

                    {/* F1 */}
                    <td className="px-5 py-3.5 font-mono text-xs font-black text-neutral-800 dark:text-neutral-200">
                      {row.f1.toFixed(4)}
                    </td>

                    {/* Precision */}
                    <td className="px-5 py-3.5 font-mono text-xs text-neutral-500 dark:text-neutral-400">
                      {row.precision.toFixed(2)}%
                    </td>

                    {/* Recall */}
                    <td className="px-5 py-3.5 font-mono text-xs text-neutral-500 dark:text-neutral-400">
                      {row.recall.toFixed(2)}%
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        {!cmpLoading && filteredCmp.length > 0 && (
          <div className="border-t border-neutral-100 px-6 py-3 dark:border-neutral-800">
            <p className="text-[11px] font-semibold text-neutral-400 dark:text-neutral-500">
              Showing {filteredCmp.length} of {comparison.length} model evaluations · sorted by accuracy
            </p>
          </div>
        )}
      </motion.div>

      {/* ── Experiment Detail Drawer ─────────────────────────────────── */}
      <AnimatePresence>
        {selected && (
          <>
            <motion.div
              className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setSelected(null)}
            />
            <motion.aside
              className="fixed right-0 top-0 z-50 flex h-full w-full max-w-lg flex-col overflow-y-auto border-l border-neutral-200 bg-white shadow-2xl dark:border-neutral-800 dark:bg-neutral-900"
              initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}
              transition={{ type: 'tween', duration: 0.28, ease: 'easeInOut' }}
            >
              {/* Gradient header */}
              {(() => {
                const m = EXP_META[selected.id] ?? { short: '', label: selected.name, gradient: 'from-neutral-600 to-neutral-800', badge: '' }
                return (
                  <div className={`relative overflow-hidden bg-gradient-to-br ${m.gradient} px-6 py-7 text-white`}>
                    <div className="pointer-events-none absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/5 blur-2xl" />
                    <div className="relative flex items-start justify-between gap-3">
                      <div>
                        <span className="rounded-full bg-white/15 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-widest">{m.short}</span>
                        <h2 className="mt-2 text-xl font-black leading-tight">{m.label}</h2>
                        <p className="mt-1 text-sm text-white/70">{selected.date}</p>
                      </div>
                      <button onClick={() => setSelected(null)}
                        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/10 text-white/80 transition-colors hover:bg-white/20">
                        <X size={18} />
                      </button>
                    </div>
                    {/* Key stats inline */}
                    <div className="relative mt-5 grid grid-cols-3 gap-3">
                      {[
                        { label: 'Accuracy', value: `${selected.accuracy.toFixed(1)}%` },
                        { label: 'F1 Score', value: selected.f1.toFixed(3) },
                        { label: 'Models',   value: selected.models },
                      ].map(({ label, value }) => (
                        <div key={label} className="rounded-xl bg-white/10 px-3 py-2.5">
                          <p className="text-[9px] font-bold uppercase tracking-widest text-white/60">{label}</p>
                          <p className="mt-0.5 text-lg font-black">{value}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )
              })()}

              {/* Body */}
              <div className="flex-1 space-y-4 p-6">

                {/* Dataset & Runtime */}
                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    { label: 'Dataset', value: selected.dataset ?? 'N/A' },
                    { label: 'Runtime', value: selected.runtime ?? 'Completed' },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-xl border border-neutral-100 bg-neutral-50/60 p-4 dark:border-neutral-800 dark:bg-neutral-800/20">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">{label}</p>
                      <p className="mt-1.5 text-sm font-bold text-neutral-900 dark:text-white">{value}</p>
                    </div>
                  ))}
                </div>

                {/* Notes */}
                {selected.notes && (
                  <div className="rounded-xl border border-neutral-100 bg-neutral-50/60 p-4 dark:border-neutral-800 dark:bg-neutral-800/20">
                    <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Research Notes</p>
                    <p className="text-xs leading-6 text-neutral-600 dark:text-neutral-400">{selected.notes}</p>
                  </div>
                )}

                {/* Hyperparameters */}
                {selected.params && (
                  <div className="rounded-xl border border-neutral-100 bg-neutral-50/60 p-4 dark:border-neutral-800 dark:bg-neutral-800/20">
                    <div className="mb-3 flex items-center justify-between">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">Hyperparameters</p>
                      <button onClick={() => downloadCSV([selected], `experiment-${selected.id}`)}
                        className="flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-2.5 py-1 text-[11px] font-bold text-neutral-600 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-neutral-300">
                        <FileSpreadsheet size={12} /> Export
                      </button>
                    </div>
                    <div className="space-y-1.5">
                      {Object.entries(selected.params).map(([k, v]) => (
                        <div key={k} className="flex items-center justify-between rounded-lg border border-neutral-100 bg-white px-3.5 py-2.5 dark:border-neutral-800 dark:bg-neutral-900">
                          <span className="text-xs font-bold text-neutral-700 dark:text-neutral-300">{k}</span>
                          <span className="font-mono text-[11px] text-neutral-500 dark:text-neutral-400">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Models in this experiment */}
                <div className="rounded-xl border border-neutral-100 bg-neutral-50/60 p-4 dark:border-neutral-800 dark:bg-neutral-800/20">
                  <p className="mb-3 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
                    Models in this experiment ({comparison.filter(r => r.experiment === selected.id).length})
                  </p>
                  <div className="space-y-1.5">
                    {comparison
                      .filter(r => r.experiment === selected.id)
                      .map((r, i) => {
                        const fm = FAMILY_META[r.family] ?? { label: r.family, color: 'bg-neutral-100 text-neutral-600', dot: 'bg-neutral-400' }
                        return (
                          <div key={r.model} className="flex items-center justify-between rounded-lg border border-neutral-100 bg-white px-3.5 py-2.5 dark:border-neutral-800 dark:bg-neutral-900">
                            <div className="flex items-center gap-2.5">
                              <span className="text-xs font-bold text-neutral-400 dark:text-neutral-500">#{i + 1}</span>
                              <span className="text-xs font-bold text-neutral-800 dark:text-neutral-200">{r.model}</span>
                              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-bold ${fm.color}`}>
                                <span className={`h-1.5 w-1.5 rounded-full ${fm.dot}`} />{fm.label}
                              </span>
                            </div>
                            <span className="font-mono text-xs font-black text-neutral-700 dark:text-neutral-300">{r.accuracy.toFixed(1)}%</span>
                          </div>
                        )
                      })
                    }
                  </div>
                </div>
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>

    </div>
  )
}
