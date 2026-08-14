import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import {
  AlertCircle, Brain, CheckCircle2, ChevronDown, Clock, ExternalLink, FileText, Globe,
  Info, Link2, Search, Sparkles, Zap,
} from 'lucide-react'
import api, { getApiErrorMessage } from '@services/api'
import { analyzeLink, type LinkAnalysisResult } from '@services/predictService'
import { experimentTitle } from '../utils/modelGroup'
import { useToast } from '../contexts/ToastContext'

interface ModelData {
  id: string; name: string; type: string
  experiment?: string; experimentName?: string
  accuracy: number; f1: number; precision: number; recall: number; status: string
}

const pct = (v: number) => `${v.toFixed(1)}%`
const EXAMPLES = [
  { label: 'BBC Somali', url: 'https://www.bbc.com/somali' },
  { label: 'Radio Dalsan', url: 'https://www.radiodalsan.com' },
  { label: 'SNTV', url: 'https://www.sntv.so' },
  { label: 'Caasimada Online', url: 'https://caasimada.net' },
]


/* Half-circle gauge, identical in shape and colour to the one on the Predict page so a
   reader moving between the two reads the same figure the same way. */
function ConfidenceGauge({ value, label }: { value: number; label: string }) {
  const clamped = Math.min(Math.max(value, 0), 1)
  const radius = 54
  const half = Math.PI * radius
  const dash = clamped * half
  const stops = label === 'AI' ? ['#2563EB', '#60A5FA'] : ['#F97316', '#FBBF24']
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="140" height="80" viewBox="0 0 140 80" className="overflow-visible">
        <defs>
          <linearGradient id="linkGaugeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor={stops[0]} />
            <stop offset="100%" stopColor={stops[1]} />
          </linearGradient>
        </defs>
        <path d={`M 16 72 A ${radius} ${radius} 0 0 1 124 72`} fill="none"
              stroke="rgba(255,255,255,0.25)" strokeWidth="10" strokeLinecap="round" />
        <motion.path
          d={`M 16 72 A ${radius} ${radius} 0 0 1 124 72`} fill="none"
          stroke="url(#linkGaugeGrad)" strokeWidth="10" strokeLinecap="round"
          strokeDasharray={`${half}`}
          initial={{ strokeDashoffset: half }}
          animate={{ strokeDashoffset: half - dash }}
          transition={{ duration: 1, ease: 'easeOut', delay: 0.2 }}
        />
        <text x="70" y="58" textAnchor="middle" fontSize="22" fontWeight="800" fill="#FFFFFF">
          {Math.round(clamped * 100)}
        </text>
      </svg>
      <span className="text-[10px] font-bold uppercase tracking-widest text-white/70">
        Confidence %
      </span>
    </div>
  )
}

export default function LinkAnalysis() {
  const { showToast } = useToast()
  const [url, setUrl]                 = useState('')
  const [busy, setBusy]               = useState(false)
  const [result, setResult]           = useState<LinkAnalysisResult | null>(null)
  const [error, setError]             = useState<string | null>(null)
  const [elapsed, setElapsed]         = useState<number | null>(null)

  const [models, setModels]           = useState<ModelData[]>([])
  const [modelsLoading, setLoading]   = useState(true)
  const [selectedCat, setSelectedCat] = useState('All Experiments')
  const [selectedModel, setSelected]  = useState('')

  useEffect(() => {
    api.get<ModelData[]>('/models')
      .then(res => {
        const raw = (Array.isArray(res.data) ? res.data : []) as ModelData[]
        setModels(raw)
        // Default to the strongest active model so the first result is the best one.
        const best = raw.filter(m => m.status === 'active')
          .sort((a, b) => (b.accuracy ?? 0) - (a.accuracy ?? 0))[0]
        if (best) setSelected(best.id)
      })
      .catch(() => showToast('Could not load the model list', 'error'))
      .finally(() => setLoading(false))
  }, [showToast])

  const categories = useMemo(
    () => Array.from(new Set(models.map(m => m.experimentName || m.experiment).filter(Boolean))) as string[],
    [models],
  )
  const catModels = useMemo(
    () => selectedCat === 'All Experiments'
      ? models
      : models.filter(m => (m.experimentName || m.experiment) === selectedCat),
    [models, selectedCat],
  )
  const selModel = models.find(m => m.id === selectedModel)
  const bestModel = useMemo(
    () => models.filter(m => m.status === 'active').sort((a, b) => (b.accuracy ?? 0) - (a.accuracy ?? 0))[0],
    [models],
  )

  const run = async () => {
    const trimmed = url.trim()
    if (!trimmed) return
    setBusy(true); setError(null); setResult(null); setElapsed(null)
    const started = performance.now()
    try {
      const data = await analyzeLink(trimmed, selectedModel || undefined)
      setResult(data)
      setElapsed(Math.round(performance.now() - started))
    } catch (err) {
      const message = getApiErrorMessage(err)
      setError(message); showToast(message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const isAI = result?.prediction?.toUpperCase() === 'AI'

  return (
    <div className="space-y-6 pb-12">

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
        className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-[#0369A1] via-[#0E7490] to-[#155E75] px-7 py-7 text-white shadow-xl"
      >
        <div className="pointer-events-none absolute -right-16 -top-16 h-48 w-48 rounded-full bg-white/5 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-10 left-1/4 h-36 w-36 rounded-full bg-emerald-400/15 blur-3xl" />
        <div className="relative flex items-center justify-between gap-4">
          <div>
            <div className="mb-2.5 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-cyan-100">
              <Globe size={12} /> Article by URL
            </div>
            <h1 className="text-[1.75rem] font-extrabold leading-tight tracking-tight">Analyse Link</h1>
            <p className="mt-1 text-sm text-cyan-100/90">
              Paste a Somali article address — the page is read, classified by topic, and
              broken down into how much of it is human against machine written.
            </p>
          </div>
          <div className="hidden shrink-0 items-center gap-2 rounded-2xl bg-white/10 px-4 py-2.5 sm:flex">
            <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
            <span className="text-sm font-bold">{modelsLoading ? 'Loading…' : `${models.length} models`}</span>
            <Zap size={14} className="text-amber-300" />
          </div>
        </div>
      </motion.div>

      {/* ── Model selection ─────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900"
      >
        <div className="flex items-center gap-3 border-b border-neutral-100 px-6 py-4 dark:border-neutral-800">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-sky-50 dark:bg-sky-500/10">
            <Sparkles size={15} className="text-sky-600 dark:text-sky-400" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-neutral-900 dark:text-white">Classifier</h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Which model reads the article and each of its paragraphs
            </p>
          </div>
        </div>

        <div className="grid gap-4 p-6 sm:grid-cols-2">
          <div className="space-y-2">
            <label className="block text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
              Experiment
            </label>
            <div className="relative">
              <select
                value={selectedCat}
                disabled={modelsLoading || categories.length === 0}
                onChange={e => { setSelectedCat(e.target.value); setResult(null) }}
                className="h-11 w-full rounded-xl border border-neutral-200 bg-neutral-50 pl-4 pr-10 text-sm font-semibold text-neutral-800 transition-all focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500/20 disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
              >
                <option value="All Experiments">All Experiments ({models.length} models)</option>
                {categories.map(c => (
                  <option key={c} value={c}>
                    {experimentTitle(c)} — {models.filter(m => (m.experimentName || m.experiment) === c).length} models
                  </option>
                ))}
              </select>
              <ChevronDown size={15} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            </div>
          </div>

          <div className="space-y-2">
            <label className="block text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
              Model
            </label>
            <div className="relative">
              <select
                value={selectedModel}
                disabled={modelsLoading || catModels.length === 0}
                onChange={e => { setSelected(e.target.value); setResult(null) }}
                className="h-11 w-full rounded-xl border border-neutral-200 bg-neutral-50 pl-4 pr-10 text-sm font-semibold text-neutral-800 transition-all focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500/20 disabled:opacity-50 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
              >
                {catModels.length === 0
                  ? <option>No models</option>
                  : catModels.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.id === bestModel?.id ? '⭐ ' : ''}{m.name}
                        {m.status !== 'active' ? ' — [No file]' : ''}
                      </option>
                    ))}
              </select>
              <ChevronDown size={15} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-neutral-400" />
            </div>
          </div>
        </div>

        {selModel && (
          <div className="mx-6 mb-5 grid grid-cols-3 gap-2 rounded-xl border border-neutral-100 bg-neutral-50/60 p-4 dark:border-neutral-800 dark:bg-neutral-800/30">
            {[
              ['Accuracy', selModel.accuracy],
              ['F1', selModel.f1],
              ['Precision', selModel.precision],
            ].map(([label, value]) => (
              <div key={label as string} className="text-center">
                <div className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">{label as string}</div>
                <div className="mt-0.5 text-base font-extrabold text-neutral-800 dark:text-white">
                  {Number.isFinite(value as number) ? `${(value as number).toFixed(2)}%` : 'N/A'}
                </div>
              </div>
            ))}
          </div>
        )}
      </motion.div>

      {/* ── URL input ───────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
        className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900"
      >
        <div className="flex items-center gap-3 border-b border-neutral-100 px-6 py-4 dark:border-neutral-800">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 dark:bg-emerald-500/10">
            <Link2 size={15} className="text-emerald-600 dark:text-emerald-400" />
          </div>
          <h2 className="text-sm font-bold text-neutral-900 dark:text-white">Article address</h2>
        </div>

        <div className="space-y-3 p-6">
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="relative flex-1">
              <ExternalLink size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-neutral-400" />
              <input
                value={url}
                onChange={e => setUrl(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && !busy) run() }}
                placeholder="https://www.bbc.com/somali/articles/…"
                className="h-11 w-full rounded-xl border border-neutral-200 bg-neutral-50 pl-10 pr-4 text-sm text-neutral-800 transition-all placeholder:text-neutral-400 focus:border-sky-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-sky-500/20 dark:border-neutral-700 dark:bg-neutral-800 dark:text-white"
              />
            </div>
            <button
              onClick={run}
              disabled={busy || !url.trim()}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-cyan-600 px-6 text-sm font-bold text-white shadow-sm transition hover:from-sky-700 hover:to-cyan-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy
                ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> Reading…</>
                : <><Search size={16} /> Analyse</>}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2 text-xs text-neutral-500 dark:text-neutral-400">
            <span className="font-semibold">Try:</span>
            {EXAMPLES.map(ex => (
              <button
                key={ex.url} onClick={() => setUrl(ex.url)}
                className="rounded-full border border-neutral-200 px-3 py-1 font-medium transition hover:border-sky-400 hover:text-sky-600 dark:border-neutral-700 dark:hover:text-sky-400"
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>
      </motion.div>

      {error && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 dark:border-red-800/40 dark:bg-red-900/20"
        >
          <AlertCircle size={17} className="mt-0.5 shrink-0 text-red-600 dark:text-red-400" />
          <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
        </motion.div>
      )}

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            className="space-y-6"
          >
            {/* The article, coloured in place. Shown before the verdict: a reader who
                can see which paragraphs were flagged can weigh the number that follows,
                rather than being handed a percentage with nothing behind it. */}
            <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-neutral-100 px-6 py-4 dark:border-neutral-800">
                <div className="flex min-w-0 items-center gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-50 dark:bg-indigo-500/10">
                    <FileText size={15} className="text-indigo-600 dark:text-indigo-400" />
                  </div>
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-bold text-neutral-900 dark:text-white">
                      {result.title || 'Article text'}
                    </h2>
                    <a href={result.url} target="_blank" rel="noreferrer"
                       className="block truncate text-xs text-sky-600 hover:underline dark:text-sky-400">
                      {result.url}
                    </a>
                  </div>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-3 text-[11px] font-semibold text-neutral-600 dark:text-neutral-300">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded bg-orange-300 dark:bg-orange-500/50" /> Human
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-3 w-3 rounded bg-blue-300 dark:bg-blue-500/50" /> AI
                  </span>
                  {result.paragraphs_skipped > 0 && (
                    <span className="inline-flex items-center gap-1.5 text-neutral-400">
                      <span className="h-3 w-3 rounded bg-neutral-200 dark:bg-neutral-700" /> too short
                    </span>
                  )}
                </div>
              </div>

              {result.short_article && (
                <div className="flex items-start gap-2.5 border-b border-amber-200/70 bg-amber-50 px-6 py-3 dark:border-amber-900/40 dark:bg-amber-950/30">
                  <AlertCircle size={15} className="mt-0.5 shrink-0 text-amber-600 dark:text-amber-400" />
                  <p className="text-[12px] leading-relaxed text-amber-900 dark:text-amber-200">
                    Maqaalkani waa gaaban ({result.word_count} eray) — {result.paragraphs_scored}{' '}
                    {result.paragraphs_scored === 1 ? 'xurmo ayaa' : 'xurmo ayaa'} la qiimeeyay.
                    Natiijadu waa tilmaan, ma aha go'aan adag.
                  </p>
                </div>
              )}

              <div className="max-h-[32rem] space-y-3 overflow-y-auto px-6 py-5">
                {result.segments.map(segment => {
                  const tone = !segment.scored
                    ? 'border-l-neutral-300 bg-neutral-50 text-neutral-500 dark:border-l-neutral-600 dark:bg-neutral-800/40 dark:text-neutral-400'
                    : segment.verdict === 'AI'
                      ? 'border-l-blue-500 bg-blue-50 text-neutral-800 dark:bg-blue-500/10 dark:text-neutral-100'
                      : 'border-l-orange-500 bg-orange-50 text-neutral-800 dark:bg-orange-500/10 dark:text-neutral-100'
                  return (
                    <div key={segment.index} className={`rounded-xl border-l-4 px-4 py-3 ${tone}`}>
                      <p className="text-sm leading-relaxed">{segment.text}</p>
                      <p className="mt-1.5 text-[11px] font-semibold uppercase tracking-wide opacity-70">
                        {segment.scored
                          ? `${segment.verdict === 'AI' ? 'AI' : 'Human'} · ${segment.words} words${
                              typeof segment.confidence === 'number'
                                ? ` · ${(segment.confidence * 100).toFixed(1)}% accurate at this length`
                                : ' · accuracy not measured for this model'}`
                          : `${segment.words} words — too short to score`}
                      </p>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Verdict card — the Predict page's classification result, without its
                publish controls, which do not apply to a fetched article. */}
            <div className={`overflow-hidden rounded-2xl shadow-lg ${
              isAI
                ? 'bg-gradient-to-br from-blue-600 via-blue-700 to-blue-900'
                : 'bg-gradient-to-br from-orange-500 via-orange-600 to-amber-700'
            }`}>
              <div className="relative px-8 py-7">
                <div className="pointer-events-none absolute inset-0 overflow-hidden">
                  <div className={`absolute -right-16 -top-16 h-48 w-48 rounded-full blur-3xl ${isAI ? 'bg-blue-300/20' : 'bg-amber-300/20'}`} />
                  <div className={`absolute -bottom-12 left-1/3 h-32 w-32 rounded-full blur-3xl ${isAI ? 'bg-cyan-400/15' : 'bg-orange-200/15'}`} />
                </div>

                <div className="relative flex flex-col items-center gap-5 text-center sm:flex-row sm:text-left">
                  <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-white/15 shadow-xl">
                    {isAI ? <Brain size={30} className="text-white" /> : <CheckCircle2 size={30} className="text-white" />}
                  </div>

                  <div className="flex-1">
                    <p className="text-[11px] font-bold uppercase tracking-widest text-white/60">Classification Result</p>
                    <h2 className="mt-1 text-4xl font-black tracking-tight text-white">
                      {isAI ? 'AI Generated' : 'Human Written'}
                    </h2>
                    <p className="mt-1.5 text-base font-semibold text-white/75">
                      {isAI
                        ? 'This article was likely produced by an AI language model.'
                        : 'This article appears to be authored by a human writer.'}
                    </p>
                    {result.category && result.category !== 'Unknown' && (
                      <div className="mt-3">
                        <span className="inline-flex items-center gap-2 rounded-full bg-white px-4 py-1.5 text-sm font-bold text-slate-900 shadow-lg shadow-black/15 ring-1 ring-black/5">
                          <span className="text-base leading-none">{result.category_icon}</span>
                          <span>{result.category}</span>
                          <span className="border-l border-slate-300 pl-2 text-[10px] font-bold uppercase tracking-widest text-slate-500">Topic</span>
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="shrink-0">
                    {typeof result.confidence === 'number' && (
                      <ConfidenceGauge value={result.confidence} label={result.prediction} />
                    )}
                  </div>
                </div>

                <div className="relative mt-6 flex flex-wrap items-center gap-3 border-t border-white/15 pt-5">
                  {[
                    { icon: <Zap size={12} />, label: selModel?.name ?? result.model },
                    { icon: <Clock size={12} />, label: elapsed ? `${(elapsed / 1000).toFixed(1)}s` : '—' },
                    { icon: <CheckCircle2 size={12} />, label: `${((result.confidence ?? 0) * 100).toFixed(0)}% confidence` },
                    { icon: <FileText size={12} />, label: `${result.word_count.toLocaleString()} words` },
                  ].map(({ icon, label }) => (
                    <span key={label} className="inline-flex items-center gap-1.5 rounded-full bg-white/20 px-3 py-1 text-xs font-semibold text-white">
                      {icon} {label}
                    </span>
                  ))}
                </div>

                <p className="relative mt-4 text-[11px] leading-relaxed text-white/80">
                  {selModel
                    ? `${selModel.id === bestModel?.id ? '\u2b50 ' : ''}${selModel.name} wuxuu leeyahay ${selModel.accuracy?.toFixed(2)}% test accuracy. `
                    : ''}
                  Natiijadan waa saadaal tirakoob ku salaysan, ma aha xaqiiq 100% ah \u2014
                  {` ${((result.confidence ?? 0) * 100).toFixed(0)}%`} kalsooni ma macnaheedu aha in ay had iyo jeer sax tahay.
                </p>
              </div>
            </div>

            {/* Probability distribution — same shape as Predict */}
            <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white p-6 shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900">
              <p className="mb-5 text-[10px] font-bold uppercase tracking-widest text-neutral-400 dark:text-neutral-500">
                Probability Distribution
              </p>
              <div className="space-y-5">
                {(['AI', 'HUMAN'] as const).map(lbl => {
                  const val = result.probabilities?.[lbl] ?? 0
                  const winner = result.prediction === lbl
                  return (
                    <div key={lbl}>
                      <div className="mb-2 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`h-2.5 w-2.5 rounded-full ${lbl === 'AI' ? 'bg-blue-500' : 'bg-orange-500'}`} />
                          <span className={`text-sm font-bold ${winner ? 'text-neutral-900 dark:text-white' : 'text-neutral-500 dark:text-neutral-400'}`}>
                            {lbl === 'AI' ? 'AI Generated' : 'Human Written'}
                          </span>
                          {winner && (
                            <span className="rounded-full bg-neutral-900 px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-wider text-white dark:bg-white dark:text-neutral-900">
                              WINNER
                            </span>
                          )}
                        </div>
                        <span className="font-mono text-lg font-black text-neutral-900 dark:text-white">
                          {Math.round(val * 100)}%
                        </span>
                      </div>
                      <div className="relative h-3 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${Math.min(val * 100, 100)}%` }}
                          transition={{ duration: 1, ease: 'easeOut', delay: 0.1 }}
                          className={`absolute inset-y-0 left-0 rounded-full ${
                            lbl === 'AI'
                              ? 'bg-gradient-to-r from-blue-500 to-blue-400'
                              : 'bg-gradient-to-r from-orange-500 to-amber-400'
                          }`}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                {[
                  ['Model family', selModel?.type ?? 'Traditional Model'],
                  ['F1 score', selModel ? selModel.f1?.toFixed(2) : '—'],
                  ['Model acc.', selModel ? `${selModel.accuracy?.toFixed(2)}%` : '—'],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-neutral-100 bg-neutral-50/60 p-4 dark:border-neutral-800 dark:bg-neutral-800/30">
                    <div className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">{label}</div>
                    <div className="mt-1 text-base font-extrabold text-neutral-800 dark:text-white">{value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* The proportion — the part unique to a fetched article. Withheld for a
                short item, where it could only ever read 100/0 and would overstate
                the evidence behind it. */}
            {result.short_article ? (
              <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white p-6 shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900">
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-50 dark:bg-violet-500/10">
                    <Zap size={15} className="text-violet-600 dark:text-violet-400" />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-neutral-900 dark:text-white">
                      No paragraph breakdown for this article
                    </h2>
                    <p className="mt-1 text-xs leading-relaxed text-neutral-500 dark:text-neutral-400">
                      At {result.word_count} words there is too little text for a paragraph
                      split to mean anything — only {result.paragraphs_scored} of{' '}
                      {result.segments.length} paragraphs could be scored. The whole-article
                      verdict above is the figure to read. Paste a longer article to see the
                      breakdown.
                    </p>
                  </div>
                </div>
              </div>
            ) : (
            <div className="overflow-hidden rounded-2xl border border-neutral-200/70 bg-white shadow-sm dark:border-neutral-800/60 dark:bg-neutral-900">
              <div className="flex items-center gap-3 border-b border-neutral-100 px-6 py-4 dark:border-neutral-800">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-50 dark:bg-violet-500/10">
                  <Zap size={15} className="text-violet-600 dark:text-violet-400" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-neutral-900 dark:text-white">
                    How much is human, how much is AI
                  </h2>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    Counted from the paragraphs coloured above
                  </p>
                </div>
              </div>

              <div className="p-6">
                <div className="flex flex-wrap items-end gap-8">
                  <div>
                    <div className="text-5xl font-extrabold text-orange-600 dark:text-orange-400">
                      {pct(result.human_percent)}
                    </div>
                    <div className="mt-0.5 text-sm font-semibold text-neutral-600 dark:text-neutral-400">Human Written</div>
                  </div>
                  <div>
                    <div className="text-5xl font-extrabold text-blue-600 dark:text-blue-400">
                      {pct(result.ai_percent)}
                    </div>
                    <div className="mt-0.5 text-sm font-semibold text-neutral-600 dark:text-neutral-400">AI Generated</div>
                  </div>
                </div>

                <div className="mt-5 flex h-4 overflow-hidden rounded-full bg-neutral-100 dark:bg-neutral-800">
                  <div className="bg-gradient-to-r from-orange-500 to-amber-400 transition-all" style={{ width: `${result.human_percent}%` }} />
                  <div className="bg-gradient-to-r from-blue-500 to-blue-400 transition-all" style={{ width: `${result.ai_percent}%` }} />
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    ['Paragraphs scored', String(result.paragraphs_scored)],
                    ['Human / AI', `${result.human_paragraphs} / ${result.ai_paragraphs}`],
                    ['Weighted by length', `${pct(result.ai_percent_by_words)} AI`],
                    ['Too short to score', String(result.paragraphs_skipped)],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-xl border border-neutral-100 bg-neutral-50/60 p-3 text-center dark:border-neutral-800 dark:bg-neutral-800/30">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-neutral-400">{label}</div>
                      <div className="mt-0.5 text-sm font-extrabold text-neutral-800 dark:text-white">{value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            )}

            {/* The caveat, beside the number it qualifies */}
            <div className="flex items-start gap-3 rounded-2xl border border-sky-200 bg-sky-50 p-5 dark:border-sky-900/40 dark:bg-sky-950/30">
              <Info size={17} className="mt-0.5 shrink-0 text-sky-600 dark:text-sky-400" />
              <p className="text-sm leading-relaxed text-sky-900 dark:text-sky-200">{result.accuracy_note}</p>
            </div>

          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
