import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { AlertTriangle, RefreshCw, X } from 'lucide-react'
import api from '@services/api'

const EXPERIMENTS = [
  { id: 'experiment_1_stopwords_included', label: 'Experiment 1', sub: 'Stopwords Included' },
  { id: 'experiment_2_stopwords_removed',  label: 'Experiment 2', sub: 'Stopwords Removed'  },
]

interface ShapFeature { feature: string; importance: number }
interface ErrorRow    { text: string; true_label: string; predicted_label: string }

const labelBadge = (label: string) => {
  const m: Record<string, string> = {
    AI:    'bg-violet-100 text-violet-700 dark:bg-violet-500/15 dark:text-violet-400',
    HUMAN: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-400',
  }
  return m[label] ?? 'bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400'
}

export default function XAI() {
  const [exp, setExp]               = useState(EXPERIMENTS[0].id)
  const [shapData, setShapData]     = useState<ShapFeature[]>([])
  const [shapLoading, setShapLoading] = useState(true)
  const [errors, setErrors]         = useState<ErrorRow[]>([])
  const [errLoading, setErrLoading] = useState(true)
  const [limeIdx, setLimeIdx]           = useState(0)
  const [limeUrl, setLimeUrl]           = useState<string | null>(null)
  const [limeLoading, setLimeLoading]   = useState(true)
  const [plotUrl, setPlotUrl]           = useState<string | null>(null)
  const [plotLoading, setPlotLoading]   = useState(true)
  const [showPlot, setShowPlot]         = useState(false)
  const prevBlob  = useRef<string | null>(null)
  const prevPlot  = useRef<string | null>(null)

  // SHAP data
  useEffect(() => {
    let cancelled = false
    setShapLoading(true)
    setShapData([])
    api.get<ShapFeature[]>(`/experiments/xai/shap/${exp}`, { params: { limit: 20 } })
      .then(r => { if (!cancelled) setShapData(Array.isArray(r.data) ? r.data : []) })
      .catch(() => { if (!cancelled) setShapData([]) })
      .finally(() => { if (!cancelled) setShapLoading(false) })
    return () => { cancelled = true }
  }, [exp])

  // Error analysis
  useEffect(() => {
    let cancelled = false
    setErrLoading(true)
    setErrors([])
    api.get<ErrorRow[]>(`/experiments/xai/errors/${exp}`)
      .then(r => { if (!cancelled) setErrors(Array.isArray(r.data) ? r.data : []) })
      .catch(() => { if (!cancelled) setErrors([]) })
      .finally(() => { if (!cancelled) setErrLoading(false) })
    return () => { cancelled = true }
  }, [exp])

  // SHAP summary plot image
  useEffect(() => {
    let cancelled = false
    setPlotLoading(true)
    setPlotUrl(null)
    api.get<ArrayBuffer>(`/experiments/xai/shap-plot/${exp}`, { responseType: 'arraybuffer' })
      .then(r => {
        if (cancelled) return
        const blob = new Blob([r.data], { type: 'image/png' })
        const url  = URL.createObjectURL(blob)
        if (prevPlot.current) URL.revokeObjectURL(prevPlot.current)
        prevPlot.current = url
        setPlotUrl(url)
      })
      .catch(() => { if (!cancelled) setPlotUrl(null) })
      .finally(() => { if (!cancelled) setPlotLoading(false) })
    return () => {
      cancelled = true
      if (prevPlot.current) { URL.revokeObjectURL(prevPlot.current); prevPlot.current = null }
    }
  }, [exp])

  // LIME
  useEffect(() => {
    setLimeLoading(true)
    setLimeUrl(null)
    api.get<string>(`/experiments/xai/lime/${exp}/${limeIdx}`)
      .then(r => {
        const blob = new Blob([r.data], { type: 'text/html' })
        const url  = URL.createObjectURL(blob)
        if (prevBlob.current) URL.revokeObjectURL(prevBlob.current)
        prevBlob.current = url
        setLimeUrl(url)
      })
      .catch(() => setLimeUrl(null))
      .finally(() => setLimeLoading(false))
    return () => {
      if (prevBlob.current) URL.revokeObjectURL(prevBlob.current)
    }
  }, [exp, limeIdx])

  const maxImp = shapData[0]?.importance ?? 1

  return (
    <div className="space-y-6 pb-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-neutral-900 dark:text-white">
          Explainability
        </h1>
        <p className="mt-0.5 text-sm text-neutral-500 dark:text-neutral-500">
          SHAP global feature importance · LIME explanations · error analysis
        </p>
      </div>

      {/* Experiment tabs */}
      <div className="flex flex-wrap gap-2">
        {EXPERIMENTS.map(e => (
          <button key={e.id} onClick={() => { setExp(e.id); setLimeIdx(0) }}
            className={`rounded-xl px-4 py-2 text-sm font-bold transition-colors ${
              exp === e.id
                ? 'bg-sky-500 text-white shadow-sm'
                : 'border border-neutral-200 bg-white text-neutral-600 hover:bg-neutral-50 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-neutral-400 dark:hover:bg-white/8'
            }`}
          >
            {e.label}
            <span className={`ml-1.5 text-xs font-normal ${exp === e.id ? 'text-sky-100' : 'text-neutral-400 dark:text-neutral-600'}`}>
              {e.sub}
            </span>
          </button>
        ))}
      </div>

      {/* ── SHAP Section ─────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white dark:border-white/[0.06] dark:bg-[#0D2137]">
        <div className="border-b border-neutral-100 px-5 py-4 dark:border-white/[0.05]">
          <h2 className="text-base font-bold text-neutral-900 dark:text-white">
            Global Feature Importance (SHAP)
          </h2>
          <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-500">
            Top 20 words by mean absolute SHAP value — higher = stronger influence on model decisions
          </p>
        </div>

        <div className="grid xl:grid-cols-[1fr_260px]">
          {/* Chart */}
          <div className="h-[520px] p-5">
            {shapLoading ? (
              <div className="flex h-full items-center justify-center">
                <RefreshCw size={20} className="animate-spin text-neutral-300 dark:text-neutral-700" />
              </div>
            ) : shapData.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-neutral-400">
                No SHAP data available
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart layout="vertical" data={shapData}
                  margin={{ top: 4, right: 40, left: 10, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false}
                    stroke="rgba(148,163,184,0.08)" />
                  <XAxis type="number" tick={{ fontSize: 9, fill: '#94a3b8' }}
                    tickFormatter={v => v.toFixed(3)} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="feature" width={120}
                    tick={{ fontSize: 9.5, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    formatter={(v: number) => [v.toFixed(5), 'SHAP value']}
                    contentStyle={{
                      borderRadius: 12, fontSize: 11,
                      border: '1px solid rgba(148,163,184,0.15)',
                      background: 'rgba(7,21,33,0.95)',
                      color: '#e2e8f0',
                    }}
                    cursor={{ fill: 'rgba(14,165,233,0.05)' }}
                  />
                  <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
                    {shapData.map((_, i) => (
                      <Cell key={i}
                        fill={i < 3 ? '#0ea5e9' : i < 8 ? '#38bdf8' : '#7dd3fc'}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>

          {/* Top-10 sidebar */}
          <div className="border-t border-neutral-100 p-5 dark:border-white/[0.05] xl:border-l xl:border-t-0">
            <p className="mb-4 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-600">
              Top 10 features
            </p>
            <div className="space-y-3">
              {shapData.slice(0, 10).map((f, i) => (
                <div key={i}>
                  <div className="mb-1 flex items-center justify-between">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded text-[9px] font-black ${
                        i === 0 ? 'bg-sky-500 text-white' :
                        i === 1 ? 'bg-sky-400 text-white' :
                        i === 2 ? 'bg-sky-300 text-sky-900' :
                        'bg-neutral-100 text-neutral-500 dark:bg-neutral-800 dark:text-neutral-400'
                      }`}>{i + 1}</span>
                      <span className="truncate text-xs font-semibold text-neutral-700 dark:text-neutral-300">
                        {f.feature}
                      </span>
                    </span>
                    <span className="ml-2 shrink-0 font-mono text-[10px] text-neutral-400 dark:text-neutral-600">
                      {f.importance.toFixed(4)}
                    </span>
                  </div>
                  <div className="h-1 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
                    <motion.div
                      className="h-full rounded-full bg-sky-400"
                      initial={{ width: 0 }}
                      animate={{ width: `${(f.importance / maxImp) * 100}%` }}
                      transition={{ duration: 0.8, delay: i * 0.04, ease: 'easeOut' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── SHAP Summary Plot ────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white dark:border-white/[0.06] dark:bg-[#0D2137]">
        <div className="flex items-center justify-between border-b border-neutral-100 px-5 py-4 dark:border-white/[0.05]">
          <div>
            <h2 className="text-base font-bold text-neutral-900 dark:text-white">SHAP Summary Plot</h2>
            <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-500">
              Visual distribution of SHAP values across all test samples per feature
            </p>
          </div>
          {plotUrl && (
            <button onClick={() => setShowPlot(true)}
              className="rounded-xl border border-neutral-200 bg-neutral-50 px-3 py-1.5 text-xs font-bold text-neutral-600 transition-colors hover:bg-neutral-100 dark:border-white/[0.08] dark:bg-white/[0.04] dark:text-neutral-400 dark:hover:bg-white/8">
              Full screen
            </button>
          )}
        </div>
        <div className="flex items-center justify-center p-5">
          {plotLoading ? (
            <div className="flex h-64 items-center justify-center">
              <RefreshCw size={20} className="animate-spin text-neutral-300 dark:text-neutral-700" />
            </div>
          ) : plotUrl ? (
            <img
              src={plotUrl}
              alt="SHAP summary plot"
              onClick={() => setShowPlot(true)}
              className="max-h-[420px] w-full cursor-zoom-in rounded-xl object-contain"
            />
          ) : (
            <div className="flex h-40 flex-col items-center justify-center gap-2 text-sm text-neutral-400">
              <AlertTriangle size={18} />
              <p>SHAP summary plot not available</p>
            </div>
          )}
        </div>
      </div>

      {/* SHAP plot lightbox */}
      {showPlot && plotUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-sm"
          onClick={() => setShowPlot(false)}>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }} transition={{ duration: 0.15 }}
            className="relative max-h-[90vh] max-w-5xl overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-[#0D1B2A]"
            onClick={e => e.stopPropagation()}>
            <button onClick={() => setShowPlot(false)}
              className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-lg bg-black/20 text-white transition-colors hover:bg-black/40">
              <X size={15} />
            </button>
            <img src={plotUrl} alt="SHAP summary plot" className="max-h-[90vh] w-auto rounded-2xl object-contain" />
          </motion.div>
        </div>
      )}

      {/* ── LIME Section ─────────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white dark:border-white/[0.06] dark:bg-[#0D2137]">
        <div className="flex flex-col gap-3 border-b border-neutral-100 px-5 py-4 dark:border-white/[0.05] sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-base font-bold text-neutral-900 dark:text-white">LIME Explanations</h2>
            <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-500">
              Word-level contributions for individual predictions — green = supports class, red = opposes
            </p>
          </div>
          <div className="flex gap-1.5">
            {[0, 1, 2].map(i => (
              <button key={i} onClick={() => setLimeIdx(i)}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-colors ${
                  limeIdx === i
                    ? 'bg-sky-500 text-white'
                    : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200 dark:bg-white/5 dark:text-neutral-400 dark:hover:bg-white/8'
                }`}>
                Sample {i + 1}
              </button>
            ))}
          </div>
        </div>
        <div className="p-5">
          {limeLoading ? (
            <div className="flex h-[520px] items-center justify-center">
              <RefreshCw size={20} className="animate-spin text-neutral-300 dark:text-neutral-700" />
            </div>
          ) : limeUrl ? (
            <iframe
              src={limeUrl}
              title={`LIME sample ${limeIdx + 1}`}
              className="h-[520px] w-full rounded-xl border border-neutral-100 dark:border-white/[0.05]"
              sandbox="allow-scripts"
            />
          ) : (
            <div className="flex h-[300px] flex-col items-center justify-center gap-2 text-sm text-neutral-400">
              <AlertTriangle size={20} />
              <p>LIME explanation unavailable</p>
            </div>
          )}
        </div>
      </div>

      {/* ── Error Analysis ───────────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white dark:border-white/[0.06] dark:bg-[#0D2137]">
        <div className="border-b border-neutral-100 px-5 py-4 dark:border-white/[0.05]">
          <h2 className="text-base font-bold text-neutral-900 dark:text-white">Error Analysis</h2>
          <p className="mt-0.5 text-xs text-neutral-500 dark:text-neutral-500">
            Misclassified samples — texts where the model predicted the wrong label
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-neutral-100 dark:border-white/[0.05]">
                {['#', 'Text', 'True label', 'Predicted'].map((h, i) => (
                  <th key={i} className={`px-5 py-3.5 text-left text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-600 ${i === 0 ? 'w-10' : ''}`}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-50 dark:divide-white/[0.03]">
              {errLoading
                ? [...Array(3)].map((_, i) => (
                    <tr key={i}>
                      {[...Array(4)].map((_, j) => (
                        <td key={j} className="px-5 py-4">
                          <div className="h-3.5 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-800" style={{ width: j === 1 ? '80%' : '50%' }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : errors.length === 0
                ? (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-sm text-neutral-400">
                      No error analysis data available
                    </td>
                  </tr>
                )
                : errors.map((row, i) => (
                  <tr key={i} className="transition-colors hover:bg-neutral-50/60 dark:hover:bg-white/[0.015]">
                    <td className="px-5 py-4 font-mono text-xs font-bold text-neutral-400 dark:text-neutral-600">{i + 1}</td>
                    <td className="px-5 py-4">
                      <p className="max-w-[540px] text-xs leading-relaxed text-neutral-600 line-clamp-2 dark:text-neutral-400">
                        {row.text}
                      </p>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`rounded-lg px-2 py-0.5 text-[11px] font-bold ${labelBadge(row.true_label)}`}>
                        {row.true_label}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`rounded-lg px-2 py-0.5 text-[11px] font-bold ${labelBadge(row.predicted_label)}`}>
                        {row.predicted_label}
                      </span>
                      {row.true_label !== row.predicted_label && (
                        <span className="ml-2 text-[10px] font-black text-red-500 dark:text-red-400">✗</span>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  )
}
