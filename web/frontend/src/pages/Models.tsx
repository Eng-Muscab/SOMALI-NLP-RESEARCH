import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Zap, TrendingUp, Activity, Cpu, RefreshCw, PlayCircle,
  AlertCircle, CheckCircle2, Star, ChevronRight,
} from 'lucide-react'
import api, { getApiErrorMessage } from '../services/api'
import { getCategoryGroup } from '../utils/modelGroup'
import { getTrainingStatus, reloadModels, startTraditionalTraining } from '../services/trainService'

interface ModelData {
  id: string; name: string; type: string
  accuracy: number; f1: number; status: string
  experiment?: string; experimentName?: string; path?: string
}

/* ── Category config ─────────────────────────────────────────────────────── */
const CAT_META: Record<string, { label: string; color: string; bg: string; dot: string }> = {
  'Traditional Model': { label: 'Traditional ML', color: 'text-sky-600 dark:text-sky-300',  bg: 'bg-sky-100 dark:bg-sky-500/15',    dot: '#0EA5E9' },
  'Traditional':       { label: 'Traditional ML', color: 'text-sky-600 dark:text-sky-300',  bg: 'bg-sky-100 dark:bg-sky-500/15',    dot: '#0EA5E9' },
  'Deep Learning':     { label: 'Deep Learning',  color: 'text-amber-600 dark:text-amber-300', bg: 'bg-amber-100 dark:bg-amber-500/15', dot: '#F59E0B' },
  'Transformer':       { label: 'Transformers',   color: 'text-violet-600 dark:text-violet-300', bg: 'bg-violet-100 dark:bg-violet-500/15', dot: '#8B5CF6' },
}
const catMeta = (t: string, p?: string) => {
  const g = getCategoryGroup(t, p)
  return CAT_META[g] ?? { label: g, color: 'text-neutral-500', bg: 'bg-neutral-100 dark:bg-neutral-800', dot: '#94A3B8' }
}

/* ── Icon by type ────────────────────────────────────────────────────────── */
const getIcon = (type: string) => {
  if (type.includes('keras') || type.includes('deep_learning')) return <Cpu size={20} />
  if (type.toLowerCase().includes('transformer') || type.includes('safetensors')) return <Zap size={20} />
  if (type.includes('forest') || type.toLowerCase().includes('ensemble')) return <Activity size={20} />
  return <TrendingUp size={20} />
}

/* ── Circular accuracy ring ──────────────────────────────────────────────── */
function AccuracyRing({ pct, color }: { pct: number; color: string }) {
  const r = 28; const circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  return (
    <svg width="72" height="72" viewBox="0 0 72 72">
      <circle cx="36" cy="36" r={r} fill="none" stroke="currentColor" strokeWidth="5" className="text-neutral-100 dark:text-neutral-800" />
      <motion.circle
        cx="36" cy="36" r={r} fill="none" stroke={color} strokeWidth="5"
        strokeLinecap="round" strokeDasharray={circ} transform="rotate(-90 36 36)"
        initial={{ strokeDashoffset: circ }}
        animate={{ strokeDashoffset: circ - dash }}
        transition={{ duration: 1.2, ease: 'easeOut' }}
      />
      <text x="36" y="40" textAnchor="middle" fontSize="13" fontWeight="800" fill={color} fontFamily="Inter,system-ui,sans-serif">
        {Math.round(pct)}%
      </text>
    </svg>
  )
}

/* ── Stat card ───────────────────────────────────────────────────────────── */
function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-2xl border border-sky-100 dark:border-sky-900/40 bg-white dark:bg-[#0D2137] px-5 py-4">
      <p className="text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-sky-600">{label}</p>
      <p className="mt-1 text-2xl font-extrabold text-sky-600 dark:text-sky-300">{value}</p>
      {sub && <p className="mt-0.5 text-[11px] font-medium text-neutral-400 dark:text-sky-700">{sub}</p>}
    </div>
  )
}

/* ── Main ────────────────────────────────────────────────────────────────── */
const TABS = ['All', 'Traditional ML', 'Deep Learning', 'Transformers']

const Models = () => {
  const [models, setModels]             = useState<ModelData[]>([])
  const [loading, setLoading]           = useState(true)
  const [error, setError]               = useState<string | null>(null)
  const [training, setTraining]         = useState(false)
  const [trainingMsg, setTrainingMsg]   = useState<string | null>(null)
  const [tab, setTab]                   = useState('All')

  const fetchModels = useCallback(async () => {
    setError(null)
    try {
      const res = await api.get<ModelData[]>('/models')
      const raw = Array.isArray(res.data) ? res.data : []
      const map = new Map<string, ModelData>()
      raw.forEach(m => { const ex = map.get(m.id); if (!ex || m.accuracy > ex.accuracy) map.set(m.id, m) })
      setModels(Array.from(map.values()))
    } catch (e) {
      setError(getApiErrorMessage(e, 'Unable to load models from the backend.'))
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { fetchModels() }, [fetchModels])

  useEffect(() => {
    if (!training) return
    const id = window.setInterval(async () => {
      try {
        const s = await getTrainingStatus()
        if (s.status === 'running') { setTrainingMsg(s.message || 'Training…'); return }
        setTraining(false)
        if (s.status === 'completed') { await reloadModels(); await fetchModels(); setTrainingMsg(s.message || 'Training complete.') }
        else if (s.status === 'failed') setTrainingMsg(s.message || 'Training failed.')
      } catch {}
    }, 3000)
    return () => window.clearInterval(id)
  }, [training, fetchModels])

  const handleTrain = async () => {
    setTrainingMsg(null); setError(null)
    try { setTraining(true); const s = await startTraditionalTraining(true); setTrainingMsg(s.message || 'Training started…') }
    catch (e) { setTraining(false); setTrainingMsg(getApiErrorMessage(e, 'Unable to start training.')) }
  }

  const handleReload = async () => {
    setError(null)
    try { await reloadModels(); await fetchModels(); setTrainingMsg('Models reloaded from disk.') }
    catch (e) { setError(getApiErrorMessage(e, 'Unable to reload models.')) }
  }

  const bestId   = models.length ? models.reduce((b, m) => m.accuracy > b.accuracy ? m : b).id : null
  const active   = models.filter(m => m.status === 'active')
  const avgAcc   = models.length ? (models.reduce((s, m) => s + m.accuracy, 0) / models.length).toFixed(1) : '—'
  const bestAcc  = models.length ? models.reduce((b, m) => m.accuracy > b.accuracy ? m : b).accuracy.toFixed(2) : '—'

  const filtered = tab === 'All' ? models : models.filter(m => {
    const cat = catMeta(m.type, m.path).label
    return cat === tab
  })

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-10 w-48 rounded-xl bg-neutral-200 dark:bg-neutral-800 animate-pulse" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-24 rounded-2xl bg-neutral-100 dark:bg-neutral-800/50 animate-pulse" />)}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[...Array(6)].map((_, i) => <div key={i} className="h-64 rounded-2xl bg-neutral-100 dark:bg-neutral-800/50 animate-pulse" />)}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-7">

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
            Models
          </h1>
          <p className="mt-1 text-sm font-medium text-neutral-500 dark:text-sky-700">
            Train and manage classifiers for AI vs Human Somali text detection
          </p>
        </div>
        <div className="flex gap-3 shrink-0">
          <button
            onClick={handleTrain} disabled={training}
            className="flex items-center gap-2 rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-bold text-white shadow-lg shadow-sky-500/25 transition-all hover:bg-sky-700 hover:-translate-y-0.5 disabled:opacity-60 disabled:translate-y-0"
          >
            <PlayCircle size={15} />
            {training ? 'Training…' : 'Train All Models'}
          </button>
          <button
            onClick={handleReload} disabled={training}
            className="flex items-center gap-2 rounded-xl border border-sky-200 bg-white px-4 py-2.5 text-sm font-bold text-sky-700 transition-all hover:bg-sky-50 hover:-translate-y-0.5 disabled:opacity-60 dark:border-sky-800/50 dark:bg-[#0D2137] dark:text-sky-300 dark:hover:bg-sky-900/30"
          >
            <RefreshCw size={14} className={training ? 'animate-spin' : ''} />
            Reload
          </button>
        </div>
      </div>

      {/* ── Stats ────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Stat label="Total Models"  value={String(models.length)}    sub={`${filtered.length} in view`} />
        <Stat label="Active"        value={String(active.length)}    sub="Ready for inference" />
        <Stat label="Avg Accuracy"  value={`${avgAcc}%`}            sub="Across all models" />
        <Stat label="Best Accuracy" value={`${bestAcc}%`}           sub="LinearSVC TFIDF" />
      </div>

      {/* ── Alerts ───────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {trainingMsg && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex items-start gap-3 rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3.5 dark:border-sky-800/40 dark:bg-sky-900/20">
            <CheckCircle2 size={16} className="mt-0.5 shrink-0 text-sky-500" />
            <p className="text-sm font-medium text-sky-800 dark:text-sky-300">{trainingMsg}</p>
          </motion.div>
        )}
        {error && (
          <motion.div initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 px-4 py-3.5 dark:border-red-800/40 dark:bg-red-900/20">
            <AlertCircle size={16} className="mt-0.5 shrink-0 text-red-500" />
            <p className="text-sm font-medium text-red-700 dark:text-red-300">{error}</p>
          </motion.div>
        )}
      </AnimatePresence>

      {models.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-neutral-200 dark:border-neutral-800 p-12 text-center space-y-3">
          <Cpu size={36} className="mx-auto text-neutral-300 dark:text-neutral-700" />
          <p className="font-bold text-neutral-600 dark:text-neutral-400">No trained models found</p>
          <p className="text-sm text-neutral-400">Click <strong>Train All Models</strong> to train Logistic Regression, LinearSVC, Random Forest, and XGBoost.</p>
        </div>
      ) : (
        <>
          {/* ── Tabs ──────────────────────────────────────────────────────── */}
          <div className="flex gap-2 flex-wrap">
            {TABS.map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-xl px-4 py-2 text-xs font-bold transition-all ${
                  tab === t
                    ? 'bg-sky-600 text-white shadow-lg shadow-sky-500/20'
                    : 'border border-neutral-200 bg-white text-neutral-500 hover:border-sky-300 hover:text-sky-600 dark:border-sky-900/40 dark:bg-[#0D2137] dark:text-sky-600 dark:hover:text-sky-300'
                }`}
              >
                {t}
                <span className={`ml-1.5 rounded-md px-1.5 py-0.5 text-[10px] font-bold ${tab === t ? 'bg-white/20' : 'bg-neutral-100 text-neutral-400 dark:bg-sky-900/30 dark:text-sky-600'}`}>
                  {t === 'All' ? models.length : models.filter(m => catMeta(m.type, m.path).label === t).length}
                </span>
              </button>
            ))}
          </div>

          {/* ── Grid ──────────────────────────────────────────────────────── */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {filtered.map((model, idx) => {
              const rec = model.id === bestId
              const cm  = catMeta(model.type, model.path)
              const isActive = model.status === 'active'
              return (
                <motion.div
                  key={model.id}
                  initial={{ opacity: 0, y: 18 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: idx * 0.06, duration: 0.35 }}
                  className={`group relative flex flex-col overflow-hidden rounded-2xl border bg-white dark:bg-[#0D2137] transition-all duration-200 hover:-translate-y-1 hover:shadow-xl ${
                    rec
                      ? 'border-sky-400/50 dark:border-sky-500/30 shadow-lg shadow-sky-500/10'
                      : 'border-neutral-200/70 dark:border-sky-900/30 hover:border-sky-300 dark:hover:border-sky-700/50'
                  }`}
                >
                  {/* Recommended ribbon */}
                  {rec && (
                    <div className="absolute right-0 top-0 z-10">
                      <div className="flex items-center gap-1 rounded-bl-xl rounded-tr-2xl bg-gradient-to-r from-sky-500 to-blue-600 px-3 py-1.5 text-[10px] font-extrabold uppercase tracking-wider text-white shadow-md">
                        <Star size={9} fill="white" /> Recommended
                      </div>
                    </div>
                  )}

                  {/* Top glow accent */}
                  {rec && <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-sky-400 via-blue-500 to-sky-400" />}

                  {/* Card header */}
                  <div className="flex items-center gap-4 px-5 pt-5 pb-4">
                    <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${cm.bg} ${cm.color}`}>
                      {getIcon(model.type)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h3 className="truncate text-[15px] font-extrabold text-neutral-900 dark:text-white" title={model.name}>
                        {model.name}
                      </h3>
                      <p className={`text-[10px] font-bold uppercase tracking-widest ${cm.color} opacity-80`}>
                        {cm.label}
                      </p>
                    </div>
                    <AccuracyRing pct={model.accuracy} color={cm.dot} />
                  </div>

                  <div className="mx-5 h-px bg-neutral-100 dark:bg-sky-900/30" />

                  {/* Body */}
                  <div className="flex flex-1 flex-col gap-4 px-5 py-4">
                    {/* Status + category row */}
                    <div className="flex items-center justify-between">
                      <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold ${
                        isActive
                          ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                          : 'bg-neutral-100 text-neutral-500 dark:bg-neutral-800/60 dark:text-neutral-400'
                      }`}>
                        <span className={`h-1.5 w-1.5 rounded-full ${isActive ? 'bg-emerald-500 animate-pulse' : 'bg-neutral-400'}`} />
                        {isActive ? 'Active' : 'Inactive'}
                      </span>
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${cm.bg} ${cm.color}`}>
                        {cm.label}
                      </span>
                    </div>

                    {/* Experiment */}
                    {model.experimentName && (
                      <div className="rounded-xl border border-neutral-100 dark:border-sky-900/30 bg-neutral-50/70 dark:bg-sky-900/10 px-3 py-2.5">
                        <p className="text-[9px] font-bold uppercase tracking-widest text-neutral-400 dark:text-sky-700">Experiment</p>
                        <p className="mt-0.5 truncate text-xs font-bold text-neutral-700 dark:text-sky-200" title={model.experimentName}>
                          {model.experimentName}
                        </p>
                      </div>
                    )}

                    {/* Metrics bars */}
                    <div className="space-y-3">
                      <div>
                        <div className="mb-1.5 flex items-end justify-between">
                          <span className="text-[10px] font-bold uppercase tracking-wide text-neutral-400 dark:text-sky-700">Accuracy</span>
                          <span className="text-sm font-extrabold text-neutral-900 dark:text-white">{model.accuracy}%</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-neutral-100 dark:bg-sky-900/30">
                          <motion.div
                            className="h-full rounded-full"
                            style={{ background: `linear-gradient(90deg, ${cm.dot}CC, ${cm.dot})` }}
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(model.accuracy, 100)}%` }}
                            transition={{ duration: 1, ease: 'easeOut', delay: idx * 0.06 + 0.2 }}
                          />
                        </div>
                      </div>

                      <div>
                        <div className="mb-1.5 flex items-end justify-between">
                          <span className="text-[10px] font-bold uppercase tracking-wide text-neutral-400 dark:text-sky-700">F1 Score</span>
                          <span className="text-sm font-extrabold text-neutral-900 dark:text-white">{model.f1}</span>
                        </div>
                        <div className="h-2 overflow-hidden rounded-full bg-neutral-100 dark:bg-sky-900/30">
                          <motion.div
                            className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-teal-500"
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.min(model.f1 * 100, 100)}%` }}
                            transition={{ duration: 1, ease: 'easeOut', delay: idx * 0.06 + 0.3 }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Footer action */}
                  <div className={`mt-auto border-t px-5 py-3.5 ${
                    isActive
                      ? 'border-sky-100/60 dark:border-sky-900/30 bg-sky-50/40 dark:bg-sky-900/10'
                      : 'border-neutral-100/60 dark:border-neutral-800/40'
                  }`}>
                    <button
                      className={`flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-xs font-bold transition-all ${
                        isActive
                          ? 'bg-gradient-to-r from-sky-500 to-sky-600 text-white shadow-md shadow-sky-500/20 hover:from-sky-600 hover:to-sky-700 hover:shadow-sky-500/30'
                          : 'border border-neutral-200 dark:border-neutral-700 text-neutral-500 dark:text-neutral-400 hover:border-neutral-300 hover:text-neutral-700'
                      }`}
                    >
                      {isActive ? 'Ready for Inference' : 'Reactivate'}
                      <ChevronRight size={13} />
                    </button>
                  </div>
                </motion.div>
              )
            })}
          </div>

          {/* ── Comparison table ──────────────────────────────────────────── */}
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
            <div className="overflow-hidden rounded-2xl border border-neutral-200/70 dark:border-sky-900/30 bg-white dark:bg-[#0D2137]">
              <div className="flex items-center gap-3 border-b border-neutral-100 dark:border-sky-900/30 px-6 py-4">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-100 dark:bg-sky-500/15 text-sky-600 dark:text-sky-400">
                  <Activity size={15} />
                </div>
                <h3 className="font-bold text-neutral-900 dark:text-white">Model Comparison</h3>
                <span className="ml-auto rounded-full bg-sky-100 dark:bg-sky-500/15 px-2.5 py-0.5 text-[11px] font-bold text-sky-700 dark:text-sky-400">
                  {models.length} models
                </span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-neutral-100 dark:border-sky-900/30 bg-neutral-50/60 dark:bg-sky-900/10">
                      {['Model', 'Category', 'Accuracy', 'F1 Score', 'Status', 'Experiment'].map(h => (
                        <th key={h} className="px-5 py-3 text-left text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-sky-700">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {models.map((model, i) => {
                      const cm = catMeta(model.type, model.path)
                      return (
                        <tr
                          key={model.id}
                          className={`border-b border-neutral-50 dark:border-sky-900/20 transition-colors hover:bg-sky-50/40 dark:hover:bg-sky-900/10 ${
                            model.id === bestId ? 'bg-sky-50/30 dark:bg-sky-900/10' : ''
                          }`}
                        >
                          <td className="px-5 py-3.5">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-neutral-900 dark:text-white">{model.name}</span>
                              {model.id === bestId && <Star size={12} className="text-sky-500" fill="#0EA5E9" />}
                            </div>
                          </td>
                          <td className="px-5 py-3.5">
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${cm.bg} ${cm.color}`}>{cm.label}</span>
                          </td>
                          <td className="px-5 py-3.5">
                            <span className="font-extrabold text-neutral-900 dark:text-white">{model.accuracy}%</span>
                          </td>
                          <td className="px-5 py-3.5">
                            <span className="font-extrabold text-neutral-900 dark:text-white">{model.f1}</span>
                          </td>
                          <td className="px-5 py-3.5">
                            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold ${
                              model.status === 'active'
                                ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400'
                                : 'bg-neutral-100 text-neutral-500 dark:bg-neutral-800/60 dark:text-neutral-400'
                            }`}>
                              <span className={`h-1.5 w-1.5 rounded-full ${model.status === 'active' ? 'bg-emerald-500' : 'bg-neutral-400'}`} />
                              {model.status === 'active' ? 'Active' : 'Inactive'}
                            </span>
                          </td>
                          <td className="px-5 py-3.5 text-xs font-medium text-neutral-500 dark:text-sky-700">
                            {model.experimentName ?? '—'}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </div>
  )
}

export default Models
